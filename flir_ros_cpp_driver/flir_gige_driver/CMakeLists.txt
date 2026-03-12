cmake_minimum_required(VERSION 3.0.2)
project(flir_gige_driver)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  sensor_msgs
  cv_bridge
  image_transport
)

find_package(OpenCV REQUIRED)

find_path(SPINNAKER_INCLUDE_DIR
  NAMES Spinnaker.h
  HINTS /opt/spinnaker/include
)

find_library(SPINNAKER_LIBRARY
  NAMES Spinnaker libSpinnaker.so
  HINTS /opt/spinnaker/lib
)

if(NOT SPINNAKER_INCLUDE_DIR OR NOT SPINNAKER_LIBRARY)
  message(FATAL_ERROR "Spinnaker SDK not found. Expected headers in /opt/spinnaker/include and library in /opt/spinnaker/lib")
endif()

catkin_package()

include_directories(
  ${catkin_INCLUDE_DIRS}
  ${OpenCV_INCLUDE_DIRS}
  ${SPINNAKER_INCLUDE_DIR}
)

add_executable(flir_gige_publisher src/flir_gige_publisher.cpp)

target_link_libraries(flir_gige_publisher
  ${catkin_LIBRARIES}
  ${OpenCV_LIBRARIES}
  ${SPINNAKER_LIBRARY}
)
