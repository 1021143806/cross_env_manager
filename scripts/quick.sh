#输入源服务器和目标服务器，指定设备型号添加至 agv_robot表
    python script.py --source-host 10.68.2.32 --source-password CCshenda889  --target-host 10.68.2.40 --target-password CCshenda889 --device-type "RTA-C060-Q-2L-410" --table agv_robot

#输入源服务器数据库，指定设备分组，到指定服务器的目标区域
python add_device_ext.py --source-host 10.68.2.27 --source-password CCshenda889  --target-host 10.68.2.40 --target-password CCshenda889   --group-name "所有四代车脚本用" --target-area 3

