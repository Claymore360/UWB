#include <cstdio>
#include <cstdint>
#include <string>
#include <exception>
#include <thread>
#include <chrono>

#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>

#include "Spinnaker.h"
#include "SpinGenApi/SpinnakerGenApi.h"

using namespace Spinnaker;
using namespace Spinnaker::GenApi;

static void safeShutdown(CameraPtr& cam, CameraList& cam_list, SystemPtr& system)
{
    try
    {
        if (cam)
        {
            try
            {
                cam->EndAcquisition();
            }
            catch (...)
            {
            }
            try
            {
                cam->DeInit();
            }
            catch (...)
            {
            }
            cam = CameraPtr();
        }
    }
    catch (...)
    {
    }

    try
    {
        cam_list.Clear();
    }
    catch (...)
    {
    }

    try
    {
        if (system)
        {
            system->ReleaseInstance();
            system = SystemPtr();
        }
    }
    catch (...)
    {
    }
}

static bool containsErrorCode(const std::string& what, const std::string& code)
{
    return what.find(code) != std::string::npos;
}

static void tuneGigETransport(CameraPtr& cam)
{
    // 在弱链路上降低包大小和发送速率，减少控制/数据冲突导致的初始化失败。
    try
    {
        INodeMap& node_map = cam->GetNodeMap();

        CIntegerPtr packet_size = node_map.GetNode("GevSCPSPacketSize");
        if (IsAvailable(packet_size) && IsWritable(packet_size))
        {
            const int64_t desired = 1500;
            const int64_t val = std::min(packet_size->GetMax(), std::max(packet_size->GetMin(), desired));
            packet_size->SetValue(val);
            ROS_INFO_STREAM("Set GevSCPSPacketSize=" << val);
        }

        CIntegerPtr inter_packet_delay = node_map.GetNode("GevSCPD");
        if (IsAvailable(inter_packet_delay) && IsWritable(inter_packet_delay))
        {
            // 轻微增加包间隔，牺牲一点吞吐换稳定性
            const int64_t desired = 1000;
            const int64_t val = std::min(inter_packet_delay->GetMax(), std::max(inter_packet_delay->GetMin(), desired));
            inter_packet_delay->SetValue(val);
            ROS_INFO_STREAM("Set GevSCPD=" << val);
        }
    }
    catch (const std::exception& e)
    {
        ROS_WARN_STREAM("GigE transport tuning skipped: " << e.what());
    }
}

static void configureContinuousAcquisition(CameraPtr& cam)
{
    try
    {
        INodeMap& node_map = cam->GetNodeMap();

        // Force non-triggered continuous mode, otherwise GetNextImage may timeout forever.
        CEnumerationPtr trigger_mode = node_map.GetNode("TriggerMode");
        if (IsAvailable(trigger_mode) && IsWritable(trigger_mode))
        {
            CEnumEntryPtr off = trigger_mode->GetEntryByName("Off");
            if (IsAvailable(off) && IsReadable(off))
            {
                trigger_mode->SetIntValue(off->GetValue());
                ROS_INFO("Set TriggerMode=Off");
            }
        }

        CEnumerationPtr acq_mode = node_map.GetNode("AcquisitionMode");
        if (IsAvailable(acq_mode) && IsWritable(acq_mode))
        {
            CEnumEntryPtr continuous = acq_mode->GetEntryByName("Continuous");
            if (IsAvailable(continuous) && IsReadable(continuous))
            {
                acq_mode->SetIntValue(continuous->GetValue());
                ROS_INFO("Set AcquisitionMode=Continuous");
            }
        }

        // Stream node map tuning for unstable networks.
        INodeMap& stream_map = cam->GetTLStreamNodeMap();
        CBooleanPtr resend = stream_map.GetNode("StreamPacketResendEnable");
        if (IsAvailable(resend) && IsWritable(resend))
        {
            resend->SetValue(true);
            ROS_INFO("Set StreamPacketResendEnable=true");
        }

        CEnumerationPtr handling = stream_map.GetNode("StreamBufferHandlingMode");
        if (IsAvailable(handling) && IsWritable(handling))
        {
            CEnumEntryPtr newest = handling->GetEntryByName("NewestOnly");
            if (IsAvailable(newest) && IsReadable(newest))
            {
                handling->SetIntValue(newest->GetValue());
                ROS_INFO("Set StreamBufferHandlingMode=NewestOnly");
            }
        }
    }
    catch (const std::exception& e)
    {
        ROS_WARN_STREAM("Acquisition mode tuning skipped: " << e.what());
    }
}

static uint32_t ipToInt(const std::string& ip)
{
    unsigned int a = 0, b = 0, c = 0, d = 0;
    if (std::sscanf(ip.c_str(), "%u.%u.%u.%u", &a, &b, &c, &d) != 4)
    {
        return 0;
    }
    return ((a & 0xFFu) << 24) | ((b & 0xFFu) << 16) | ((c & 0xFFu) << 8) | (d & 0xFFu);
}

static uint32_t bswap32(uint32_t v)
{
    return ((v & 0x000000FFu) << 24) |
           ((v & 0x0000FF00u) << 8) |
           ((v & 0x00FF0000u) >> 8) |
           ((v & 0xFF000000u) >> 24);
}

static std::string intToIp(uint32_t v)
{
    const unsigned int a = (v >> 24) & 0xFFu;
    const unsigned int b = (v >> 16) & 0xFFu;
    const unsigned int c = (v >> 8) & 0xFFu;
    const unsigned int d = v & 0xFFu;
    char buf[32] = {0};
    std::snprintf(buf, sizeof(buf), "%u.%u.%u.%u", a, b, c, d);
    return std::string(buf);
}

int main(int argc, char** argv)
{
    ros::init(argc, argv, "flir_gige_publisher");
    ros::NodeHandle nh("~");

    std::string target_ip = "192.168.123.100";
    std::string topic_name = "/camera/fisheye/image_raw";
    int fps = 15;

    nh.param<std::string>("target_ip", target_ip, target_ip);
    nh.param<std::string>("topic_name", topic_name, topic_name);
    nh.param<int>("fps", fps, fps);

    const uint32_t target_ip_int = ipToInt(target_ip);
    const uint32_t target_ip_int_swapped = bswap32(target_ip_int);
    if (target_ip_int == 0)
    {
        ROS_ERROR_STREAM("Invalid target_ip: " << target_ip);
        return 1;
    }

    ros::Publisher pub = nh.advertise<sensor_msgs::Image>(topic_name, 5);

    SystemPtr system = System::GetInstance();
    CameraList cam_list;
    CameraPtr cam;

    // GigE 网络抖动时，设备发现可能瞬时失败，做几次重试。
    const int discover_retries = 12;
    for (int i = 0; i < discover_retries; ++i)
    {
        cam_list = system->GetCameras();
        if (cam_list.GetSize() > 0)
        {
            break;
        }
        ROS_WARN_STREAM_THROTTLE(1.0, "Spinnaker found no FLIR camera, retry " << (i + 1) << "/" << discover_retries);
        ros::Duration(0.4).sleep();
    }

    if (cam_list.GetSize() == 0)
    {
        ROS_ERROR("Spinnaker found no FLIR camera.");
        safeShutdown(cam, cam_list, system);
        return 1;
    }

    int selected_index = -1;

    ROS_INFO_STREAM("Spinnaker cameras discovered: " << cam_list.GetSize());

    for (unsigned int i = 0; i < cam_list.GetSize(); ++i)
    {
        CameraPtr cand = cam_list.GetByIndex(i);
        INodeMap& node_map_tl = cand->GetTLDeviceNodeMap();
        CIntegerPtr ip_node = node_map_tl.GetNode("GevDeviceIPAddress");
        CValuePtr model_node = node_map_tl.GetNode("DeviceModelName");
        std::string model_name = "unknown";
        if (IsAvailable(model_node) && IsReadable(model_node))
        {
            model_name = model_node->ToString();
        }

        if (IsAvailable(ip_node) && IsReadable(ip_node))
        {
            const uint32_t current_ip = static_cast<uint32_t>(ip_node->GetValue());
            ROS_INFO_STREAM("Camera[" << i << "] model=" << model_name
                            << " ip_raw=" << current_ip
                            << " ip_be=" << intToIp(current_ip)
                            << " ip_le=" << intToIp(bswap32(current_ip)));

            if (current_ip == target_ip_int || current_ip == target_ip_int_swapped)
            {
                cam = cand;
                selected_index = static_cast<int>(i);
                break;
            }
        }
        else
        {
            ROS_INFO_STREAM("Camera[" << i << "] model=" << model_name << " ip=unreadable");
        }
    }

    if (!cam)
    {
        ROS_WARN_STREAM("Target FLIR IP not matched exactly: " << target_ip
                        << ". Falling back to camera index 0.");
        cam = cam_list.GetByIndex(0);
        selected_index = 0;
    }

    ROS_INFO_STREAM("Connected FLIR camera index=" << selected_index << " ip=" << target_ip);

    bool initialized = false;
    try
    {
        const int init_retries = 8;
        for (int i = 0; i < init_retries; ++i)
        {
            try
            {
                cam->Init();
                tuneGigETransport(cam);
                configureContinuousAcquisition(cam);
                cam->BeginAcquisition();
                initialized = true;
                ROS_INFO_STREAM("FLIR init success on try " << (i + 1) << "/" << init_retries);
                break;
            }
            catch (const std::exception& e)
            {
                const std::string err = e.what();
                ROS_WARN_STREAM("FLIR init try " << (i + 1) << " failed: " << err);
                try { cam->EndAcquisition(); } catch (...) {}
                try { cam->DeInit(); } catch (...) {}

                // XML 读取失败(-1010)或子网检测失败(-1015)都先等待再试。
                if (containsErrorCode(err, "[-1010]") || containsErrorCode(err, "[-1015]"))
                {
                    std::this_thread::sleep_for(std::chrono::milliseconds(600));
                    continue;
                }
                throw;
            }
        }

        if (!initialized)
        {
            throw std::runtime_error("FLIR init failed after retries");
        }

        ros::Rate rate(std::max(1, fps));
        while (ros::ok())
        {
            try
            {
                ImagePtr image = cam->GetNextImage(2000);
                if (!image->IsIncomplete())
                {
                    ImagePtr bgr = image->Convert(PixelFormat_BGR8, HQ_LINEAR);

                    cv::Mat frame(
                        static_cast<int>(bgr->GetHeight()),
                        static_cast<int>(bgr->GetWidth()),
                        CV_8UC3,
                        bgr->GetData(),
                        bgr->GetStride());

                    std_msgs::Header header;
                    header.stamp = ros::Time::now();
                    header.frame_id = "fisheye_optical_frame";

                    sensor_msgs::ImagePtr msg = cv_bridge::CvImage(header, "bgr8", frame).toImageMsg();
                    pub.publish(msg);
                }
                image->Release();
            }
            catch (const std::exception& e)
            {
                ROS_WARN_STREAM_THROTTLE(2.0, "Capture error: " << e.what());
            }

            ros::spinOnce();
            rate.sleep();
        }

        if (initialized)
        {
            cam->EndAcquisition();
            cam->DeInit();
        }
    }
    catch (const std::exception& e)
    {
        const std::string err = e.what();
        ROS_ERROR_STREAM("Fatal FLIR error: " << err);
        if (err.find("wrong subnet") != std::string::npos)
        {
            ROS_ERROR("Camera is on wrong subnet. Please configure eth0 to same subnet as camera, e.g. sudo ip addr add 169.254.100.10/16 dev eth0");
        }

        safeShutdown(cam, cam_list, system);
        return 1;
    }

    safeShutdown(cam, cam_list, system);
    return 0;
}
