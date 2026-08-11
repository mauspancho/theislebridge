cmake_minimum_required(VERSION 3.20)
project(TheIsleBridgeNative LANGUAGES CXX)

set(TARGET TheIsleBridgeNative)

add_library(${TARGET} SHARED
    TheIsleBridgeNative/src/main.cpp
)

target_compile_features(${TARGET} PRIVATE cxx_std_20)
target_compile_options(${TARGET} PRIVATE -Wall -Wextra -Wpedantic -fPIC)
target_link_libraries(${TARGET} PRIVATE pthread dl)

set_target_properties(${TARGET} PROPERTIES
    OUTPUT_NAME "TheIsleBridgeNative"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Game__Shipping__Linux64/lib"
)
