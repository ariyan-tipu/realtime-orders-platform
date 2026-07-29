cmake_minimum_required(VERSION 3.18)
project(pickpath_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(pickpath_native src/main.cpp)

install(TARGETS pickpath_native LIBRARY DESTINATION .)
