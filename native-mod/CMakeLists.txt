cmake_minimum_required(VERSION 3.20)
project(TheIsleBridgeNative LANGUAGES CXX)

set(TARGET TheIsleBridgeNative)

if(NOT DEFINED UE4SS_ROOT OR UE4SS_ROOT STREQUAL "")
    message(FATAL_ERROR "UE4SS_ROOT is required. Pass -DUE4SS_ROOT=/path/to/ue4ss-linux")
endif()

get_filename_component(UE4SS_ROOT "${UE4SS_ROOT}" ABSOLUTE)
if(NOT EXISTS "${UE4SS_ROOT}/CMakeLists.txt")
    message(FATAL_ERROR "UE4SS_ROOT does not contain CMakeLists.txt: ${UE4SS_ROOT}")
endif()

if(NOT TARGET UE4SS)
    add_subdirectory("${UE4SS_ROOT}" "${CMAKE_BINARY_DIR}/ue4ss-build" EXCLUDE_FROM_ALL)
endif()

add_library(${TARGET} SHARED
    TheIsleBridgeNative/src/main.cpp
)

target_compile_features(${TARGET} PRIVATE cxx_std_20)
target_compile_options(${TARGET} PRIVATE -Wall -Wextra -Wpedantic -fPIC)
target_link_libraries(${TARGET} PUBLIC UE4SS)
target_link_libraries(${TARGET} PRIVATE pthread dl)

set_target_properties(${TARGET} PROPERTIES
    OUTPUT_NAME "TheIsleBridgeNative"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/Game__Shipping__Linux64/lib"
)
