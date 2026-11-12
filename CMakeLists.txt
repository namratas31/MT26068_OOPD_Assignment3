cmake_minimum_required(VERSION 3.16)

project(PandemicSimulation LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_executable(PandemicSimulation
    src/main.cpp
    src/Grid.cpp
    src/Random.cpp
    src/Simulation.cpp
)

target_include_directories(PandemicSimulation
    PRIVATE include
)

target_link_libraries(PandemicSimulation
    PRIVATE Threads::Threads
)

target_compile_options(PandemicSimulation
    PRIVATE -Wall -Wextra
)
