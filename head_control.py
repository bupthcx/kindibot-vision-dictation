#!/usr/bin/env python3
# head_control.py
import sys
import rospy
import rospkg
sys.path.append(rospkg.RosPack().get_path('leju_lib_pkg'))
from bodyhub.msg import JointControlPoint
from bodyhub.srv import SrvTLSstring
import motion.bodyhub_client as bodycli

def get_control_id():
    try:
        rospy.wait_for_service('MediumSize/BodyHub/GetMasterID', 1)
        client = rospy.ServiceProxy('MediumSize/BodyHub/GetMasterID', SrvTLSstring)
        return client('get').data
    except:
        print("获取controlID失败，使用默认值2")
        return 2

def set_head(pub, control_id, horizontal=0, vertical=0):
    horizontal = max(-75, min(75, horizontal))
    vertical = max(-25, min(25, vertical))
    pub.publish(positions=[horizontal, vertical], mainControlID=control_id)
    print(f"已发送头部角度：水平={horizontal}, 垂直={vertical}")

if __name__ == '__main__':
    rospy.init_node('head_control_test', anonymous=True)
    bodycli.BodyhubClient(2).ready()

    pub = rospy.Publisher('MediumSize/BodyHub/HeadPosition',
                          JointControlPoint, queue_size=10)
    rospy.sleep(0.5)
    control_id = get_control_id()

    print("=== 头部控制测试 ===")
    print("1. 低头（垂直=+20度）")
    print("2. 抬头（垂直=-20度）")
    print("3. 左转（水平=-30度）")
    print("4. 右转（水平=+30度）")
    print("5. 复位")
    print("6. 自定义角度")
    choice = input("请选择：").strip()

    if choice == '1':
        set_head(pub, control_id, 0, 20)
    elif choice == '2':
        set_head(pub, control_id, 0, -20)
    elif choice == '3':
        set_head(pub, control_id, -30, 0)
    elif choice == '4':
        set_head(pub, control_id, 30, 0)
    elif choice == '5':
        set_head(pub, control_id, 0, 0)
    elif choice == '6':
        h = int(input("水平角度（±75）：").strip())
        v = int(input("垂直角度（±25）：").strip())
        set_head(pub, control_id, h, v)

    rospy.sleep(2)
    set_head(pub, control_id, 0, 0)
    print("已复位")