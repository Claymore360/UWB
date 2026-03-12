# FLIR ROS C++ Publisher (Migration Copy)

This folder stores a migration copy of the FLIR GigE ROS C++ publisher package.

## Layout

- `flir_gige_driver/src/flir_gige_publisher.cpp`
- `flir_gige_driver/launch/flir_gige_publisher.launch`
- `flir_gige_driver/CMakeLists.txt`
- `flir_gige_driver/package.xml`

## Build (in catkin workspace)

Copy `flir_gige_driver` into your catkin workspace `src/` and build:

```bash
cd <catkin_ws>
catkin_make -DCATKIN_WHITELIST_PACKAGES=flir_gige_driver
```

## Run

```bash
source /opt/ros/noetic/setup.bash
source <catkin_ws>/devel/setup.bash
export LD_LIBRARY_PATH=/opt/spinnaker/lib:$LD_LIBRARY_PATH
export GENICAM_GENTL64_PATH=/opt/spinnaker/lib/flir-gentl
roslaunch flir_gige_driver flir_gige_publisher.launch
```

Default topic: `/camera/fisheye/image_raw`
