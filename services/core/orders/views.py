import time

from django.conf import settings
from django.http import Http404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

import pickpath
from config.permissions import IsOperator
from inventory.models import Stock
from orders.demo import advance_random_orders, demo_user, place_random_order
from orders.models import Order, OrderStatus
from orders.serializers import (
    OrderDetailSerializer,
    OrderSerializer,
    PlaceOrderSerializer,
)
from orders.services import (
    InsufficientStock,
    InvalidTransition,
    advance_order,
    place_order,
)


class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        Order.objects.select_related("warehouse")
        .prefetch_related("items__variant")
        .order_by("-created_at")
    )
    lookup_field = "public_id"

    def get_serializer_class(self) -> type[OrderSerializer]:
        return OrderDetailSerializer if self.action == "retrieve" else OrderSerializer

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        payload = PlaceOrderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        # ReadOnlyOrDemoWrite has already rejected anonymous writes outside
        # demo mode, so reaching here anonymously means demo mode is on and
        # the order belongs to the shared demo account.
        user = request.user if request.user.is_authenticated else demo_user()

        try:
            order = place_order(
                user=user,
                warehouse=payload.validated_data["warehouse"],
                lines=payload.validated_data["lines"],
            )
        except InsufficientStock as exc:
            return Response(
                {
                    "detail": str(exc),
                    "shortages": [
                        {"sku": s.sku, "requested": s.requested, "available": s.available}
                        for s in exc.shortages
                    ],
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsOperator])
    def advance(self, request: Request, public_id: str | None = None) -> Response:
        """Move one order along its lifecycle. Operators only.

        Deliberately outside the demo-mode allowance that `create` enjoys:
        cancelling returns units to stock, and `public_id` values are visible
        from the open list endpoint, so an anonymous caller who could reach
        this could move inventory for orders that are not theirs.
        """
        to_status = request.data.get("to_status", "")
        if to_status not in OrderStatus.values:
            raise ValidationError({"to_status": f"must be one of {OrderStatus.values}"})
        try:
            order = advance_order(
                self.get_object(), to_status, note=str(request.data.get("note", ""))
            )
        except InvalidTransition as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["get"], url_path="pick-path")
    def pick_path(self, request: Request, public_id: str | None = None) -> Response:
        engine = request.query_params.get("engine")
        if engine not in (None, "python", "native"):
            raise ValidationError({"engine": "must be 'python' or 'native'"})
        if engine == "native" and not pickpath.native_available():
            return Response(
                {"detail": "native engine not installed in this environment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = self.get_object()
        items = order.items.select_related("variant")
        stock_by_variant = {
            stock.variant_id: stock
            for stock in Stock.objects.filter(
                warehouse=order.warehouse, variant_id__in=[item.variant_id for item in items]
            )
        }

        bins: dict[tuple[int, int], list[dict[str, object]]] = {}
        unlocated: list[str] = []
        for item in items:
            stock = stock_by_variant.get(item.variant_id)
            if stock is None:
                unlocated.append(item.variant.sku)
                continue
            bins.setdefault((stock.bin_x, stock.bin_y), []).append(
                {"sku": item.variant.sku, "quantity": item.quantity}
            )

        bin_list = sorted(bins)
        started = time.perf_counter()
        result = pickpath.optimize_route(bin_list, depot=(0, 0), engine=engine)
        elapsed_ms = (time.perf_counter() - started) * 1000

        stops = [
            {
                "seq": position,
                "x": bin_list[bin_index][0],
                "y": bin_list[bin_index][1],
                "items": bins[bin_list[bin_index]],
            }
            for position, bin_index in enumerate(result.sequence)
        ]
        return Response(
            {
                "order": str(order.public_id),
                "warehouse": {
                    "code": order.warehouse.code,
                    "grid_width": order.warehouse.grid_width,
                    "grid_height": order.warehouse.grid_height,
                },
                "depot": [0, 0],
                "engine": result.engine,
                "total_distance": result.total_distance,
                "computed_ms": round(elapsed_ms, 3),
                "stops": stops,
                "unlocated_skus": unlocated,
            }
        )


class DemoOrderView(APIView):
    """Generates realistic traffic for the live dashboard.

    One POST places a randomised order and advances up to two existing orders
    one lifecycle step. Only available when DEMO_MODE is on.
    """

    # This view runs its own, stricter gate below: outside demo mode it 404s,
    # so the endpoint does not exist rather than existing and refusing. That
    # is why it opts out of the project default instead of inheriting it.
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        if not settings.DEMO_MODE:
            raise Http404

        placed: Order | None = None
        last_error: InsufficientStock | None = None
        for _ in range(3):  # a random sample can race another shopper; resample
            try:
                placed = place_random_order()
                break
            except InsufficientStock as exc:
                last_error = exc

        advanced = advance_random_orders(limit=2)
        if placed is None and not advanced:
            detail = str(last_error) if last_error else "no sellable stock available"
            return Response({"detail": detail}, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "placed": OrderSerializer(placed).data if placed else None,
                "advanced": [
                    {"order": str(order.public_id), "status": order.status} for order in advanced
                ],
            },
            status=status.HTTP_201_CREATED if placed else status.HTTP_200_OK,
        )
