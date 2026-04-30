# #主页上排菜单

1. 任务单号查询

  1. 输入任务单号和服务器 ip 地址

    1. 任务 id，对于数据库文档中的 orderid

    2. ip 地址输入

      1. 支持输入转换 10.68.2.32

      2. 支持输入 32 单个数字，自动添加 10.68.2.，转换为 10.68.2.32

  2. 返回内容（以下内容如果需要从数据库查询则返回对应记录的一行的所有字段内容，并整理为 json，可以点击查看详细按钮查看json数据）

    1. 数据库 **task_group** 和 task_group_detail

2. 跨环境任务查询

  查询方式支持

  1. 货架号查询，逻辑查询该货架最近一条非已完成任务，查询逻辑优先查执行中，任务失败及异常等其他状态，如果都没有查到，则查询最近状态为已完成的一条，从数据库获取到任务单号之后走任务单号查询。

  2. 任务单号查询，这是唯一直接获取全部跨环境任务信息的查询

    1. 访问服务器 10.68.2.32

    2. 需要获取的信息（以下内容如果需要从数据库查询则返回对应记录的一行的所有字段，并整理为 json，可以点击查看详细按钮查看json数据）

      1. 该任务执行的任务大任务模板

        1. 该大任务模板关联的子任务模板

        2. 添加按钮支持直接跳转到模板编辑页面（该项目内）

      2. 该大大模板的其他执行中（非已完成非异常完成，包含异常任务）任务

      3. 子任务因为分布在不同服务器，所以整理数据后到通过 1 中的任务单号进行查询，然后将信息列出，md 格式，不使用隐藏窗口，直接在一个框中显示，详细可以查看获取到的报文。

以上为我架构的查询逻辑，有没有什么问题或不明确的地方，技术文档参考以下数据库表结构

# 数据库表



```Markdown
名称	类型	长度	小数点	不是 Null	虚拟	键	虚拟类型	表达式	枚举值	默认值	注释	存储	列格式	字符集	排序规则	键长度	键排序	永远生成	根据当前时间戳更新	二进制	自动递增	无符号	填充零
id	bigint			true	false	true					任务组id					0	ASC	false	false	false	true	false	false
template_code	varchar	64		false	false	false				NULL	任务模板编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
task_type	tinyint	1		false	false	false				NULL	任务类型 1:搬运 2:仓储							false	false	false	false	false	false
priority	bigint			false	false	false				NULL	任务优先级							false	false	false	false	false	false
score	bigint			false	false	false				NULL	任务分数							false	false	false	false	false	false
order_path	varchar	5000		false	false	false				NULL	路径点名称			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
path_points	varchar	5000		false	false	false				NULL	路径点集			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
area_id	int			false	false	false				NULL	区域id							false	false	false	false	false	false
status	tinyint			false	false	false				NULL	任务状态 1:未发送,2:正在取消,3:已取消,4:正在发送,5:发送失败,6:执行中,7:执行失败,8:任务完成,9:已下发							false	false	false	false	false	false
merge_tg_id	bigint			false	false	false				NULL	合并任务组id							false	false	false	false	false	false
order_id	bigint			false	false	false				NULL	订单id							false	false	false	false	false	false
out_order_id	varchar	64		false	false	false				NULL	外部订单id			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
third_order_id	varchar	100		false	false	false				NULL	第三方订单id			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
create_time	int			false	false	false				NULL	创建时间							false	false	false	false	false	false
start_time	int			false	false	false				NULL	开始时间							false	false	false	false	false	false
end_time	int			false	false	false				NULL	结束时间							false	false	false	false	false	false
robot_id	varchar	20		false	false	false				NULL	设备序列号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
robot_num	varchar	10		false	false	false				NULL	分派AGV			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
robot_type	varchar	2000		false	false	false				NULL	设备类型			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_num	varchar	200		false	false	false				NULL				utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_model	int			false	false	false				NULL	货架模型，不指定时默认取点位第一个							false	false	false	false	false	false
load_type	int			false	false	false				NULL	第三方任务负载状态							false	false	false	false	false	false
error_desc	varchar	200		false	false	false				NULL	错误描述			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
display	tinyint	1		false	false	false				1	是否在客户端展示 0:不展示 1:展示							false	false	false	false	false	false
is_sequence	tinyint	1		false	false	false				0	子任务是否必须顺序执行0:非顺序 1：顺序							false	false	false	false	false	false
is_temp	tinyint	1		false	false	false				0	临时订单0:否 1:是 默认0							false	false	false	false	false	false
materiel	varchar	3000		false	false	false				NULL	物料信息json串合并			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
work_id	int			false	false	false				NULL	工作位id							false	false	false	false	false	false
action_param	varchar	2000		false	false	false				NULL	action参数，如上料区高度、料箱宽度，json格式			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
merge_id	bigint			false	false	false				NULL	合并任务id							false	false	false	false	false	false
sub_ids	varchar	200		false	false	false				NULL	关联的子任务id集合			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
merge_status	tinyint			false	false	false				NULL	合并任务状态							false	false	false	false	false	false
storage_num	varchar	200		false	false	false				NULL	立体库库位编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
agv_task_weight	varchar	200		false	false	false				NULL	设备执行任务的权重			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
stack_storage_num	tinyint			false	false	false				NULL								false	false	false	false	false	false
carrier_type	int			false	false	false				0	载体类型0无类型 1：货架 2:栈板  3:料箱							false	false	false	false	false	false
carrier_code	varchar	200		false	false	false				NULL				utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
is_release_robot	tinyint			false	false	false				NULL	0:任务完成时释放设备 1：任务完成时不释放设备							false	false	false	false	false	false
send_time	int			false	false	false				NULL	任务下发时间							false	false	false	false	false	false
has_next_move_task_info	int			false	false	false				1	是否下发下一个移动任务的规划信息，0 不下发  1 下发							false	false	false	false	false	false
is_create_task	int			false	false	false				0	是否生成任务，0 不需要  1 需要创建   2 已创建							false	false	false	false	false	false
main_task_id	varchar	200		false	false	false				NULL	货架跨区域使用 主任务id			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
origin_task_info	varchar	1000		false	false	false				NULL	拆分任务对象信息{targetPoint,crossCode,enterQrCode,exitQrCode}			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
task_model	varchar	255		false	false	false				NULL	任务模式 commonTask coverTask  readyRelateTask			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
default_cancel_task_strategy	tinyint	1		false	false	false				1	负载取消任务策略：1默认取消动作;2指定片区域；3回原库位;							false	false	false	false	false	false
default_cancel_task_strategy_fix_point	varchar	200		false	false	false				NULL	负载取消任务指定点			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
default_cancel_task_strategy_fix_point_score	varchar	200		false	false	false				NULL	负载取消任务指定点分数			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
pre_alloc	tinyint	1		false	false	false				0	任务预分配标识							false	false	false	false	false	false
error_code	varchar	64		false	false	false				NULL	异常码，BMS接口国际化error_desc使用			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
```


```Markdown
名称	类型	长度	小数点	不是 Null	虚拟	键	虚拟类型	表达式	枚举值	默认值	注释	存储	列格式	字符集	排序规则	键长度	键排序	永远生成	根据当前时间戳更新	二进制	自动递增	无符号	填充零
id	bigint			true	false	true					子任务id					0	ASC	false	false	false	true	false	false
tg_id	bigint			false	false	false				NULL	任务组id							false	false	false	false	false	false
area_id	int			false	false	false				NULL	区域id							false	false	false	false	false	false
task_type	tinyint			false	false	false				NULL	子任务类型							false	false	false	false	false	false
task_seq	tinyint			false	false	false				NULL	子任务顺序号							false	false	false	false	false	false
point_access	tinyint			false	false	false				NULL	点位获取方式							false	false	false	false	false	false
point_type	tinyint			false	false	false				NULL	点位类型 1:电梯点 2:电梯入口点 3:电梯出口点 4:门禁点 5：扫描门入口 6扫描门出口 7：货架点 8：工作台							false	false	false	false	false	false
choose_mode	tinyint	1		false	false	false				NULL	无可用点是否继续任务：0不继续，1继续							false	false	false	false	false	false
start_point	varchar	20		false	false	false				NULL	开始点			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
end_point	varchar	512		false	false	false				NULL	结束点			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
is_virtual_point	tinyint	1		false	false	false				0	是否虚拟点位 1:是 0:否							false	false	false	false	false	false
x	int			false	false	false				NULL	x坐标							false	false	false	false	false	false
y	int			false	false	false				NULL	y坐标							false	false	false	false	false	false
action	varchar	500		false	false	false				NULL	动作			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
angel	int			false	false	false				NULL	设备目标角度							false	false	false	false	false	false
robot_id	varchar	20		false	false	false				NULL	设备序列号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
robot_num	varchar	10		false	false	false				NULL	设备编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
start_time	int			false	false	false				NULL	任务开始时间							false	false	false	false	false	false
end_time	int			false	false	false				NULL	任务结束时间							false	false	false	false	false	false
status	tinyint			false	false	false				NULL	任务状态 0:未缓存,1:已缓存未发送,2:正在取消,3:已取消,4:正在发送,5:发送失败,6:执行中,7:执行失败,8:任务完成							false	false	false	false	false	false
need_trigger	tinyint	1		false	false	false				NULL	是否需要触发 0:不需要,1:需要							false	false	false	false	false	false
trigger_type	tinyint	1		false	false	false				NULL	触发方式							false	false	false	false	false	false
notify_third	tinyint	1		false	false	false				NULL	是否需要通知第三方(0:不需要,1:需要)							false	false	false	false	false	false
notify_start	varchar	512		false	false	false				NULL				utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
notify_end	varchar	512		false	false	false				NULL				utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_num	varchar	32		false	false	false				NULL	货架id			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_model	varchar	32		false	false	false				NULL	负载模型			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_orignal_angel	int			false	false	false				NULL	货架初始角度							false	false	false	false	false	false
shelf_dest_angel	int			false	false	false				NULL	货架目标角度							false	false	false	false	false	false
choose_task	tinyint	1		false	false	false				0	选做任务，0：必做 1：选做							false	false	false	false	false	false
materiel	text			false	false	false				NULL	商品信息			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
alarm_type	tinyint			false	false	false				0	报警类型 0:不告警 1:库位告警							false	false	false	false	false	false
multi_dest_info	varchar	14000		false	false	false				NULL	多个目标点区域id、二维码、x、y信息			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
merge_id	bigint			false	false	false				NULL	合并任务id							false	false	false	false	false	false
tg_ids	varchar	200		false	false	false				NULL	关联的任务组id集合			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
action_params	varchar	200		false	false	false				NULL	action参数，json格式，根据业务定义具体的格式			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
prepare_point	varchar	100		false	false	false				NULL	准备点			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
fix_point_score	varchar	5000		false	false	false				NULL	指定点分数			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
storage_num	varchar	100		false	false	false				NULL	库位编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
auto_trigger_time	int			false	false	false				NULL	自动触发时间							false	false	false	false	false	false
follow_point	tinyint	1		false	false	false				0	是否跟随前一个任务的目标点:0:不跟随,1:跟随							false	false	false	false	false	false
config_name	varchar	30		false	false	false				NULL	目标点获取-第三方获取			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
skip_id	int			false	false	false				0	跳过条件,关联task_relation_skip 主键							false	false	false	false	false	false
load_type	int			false	false	false				NULL	子任务负载状态							false	false	false	false	false	false
trigger_over_time	int			false	false	false				NULL	触发超时时间							false	false	false	false	false	false
trigger_over_time_handle	tinyint			false	false	false				NULL	触发超时处理方式：0：任务取消，1：继续等待							false	false	false	false	false	false
task_odom	double	10	3	false	false	false				NULL	子任务行走里程							false	false	false	false	false	false
wait_time	int			false	false	false				NULL	到达排队区时间							false	false	false	false	false	false
auto_cancel_task	int			false	false	false				0	是否自动取消任务：0不允许自动取消。1允许自动取消							false	false	false	false	false	false
task_battery	double	10	3	false	false	false				0.000	任务耗电量							false	false	false	false	false	false
relation_id	int			false	false	false				0	关联 task_relation.id							false	false	false	false	false	false
```


```Markdown
名称	类型	长度	小数点	不是 Null	虚拟	键	虚拟类型	表达式	枚举值	默认值	注释	存储	列格式	字符集	排序规则	键长度	键排序	永远生成	根据当前时间戳更新	二进制	自动递增	无符号	填充零
id	bigint			true	false	true					ID					0	ASC	false	false	false	true	false	false
task_id	bigint			false	false	false				NULL	sub_task.id							false	false	false	false	false	false
tg_id	bigint			false	false	false				NULL								false	false	false	false	false	false
start_time	int			false	false	false				NULL								false	false	false	false	false	false
end_time	int			false	false	false				NULL								false	false	false	false	false	false
start_point_px	int			false	false	false				NULL								false	false	false	false	false	false
start_point_py	int			false	false	false				NULL								false	false	false	false	false	false
start_point_code	varchar	255		false	false	false				NULL				utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
start_point_angle	int			false	false	false				NULL								false	false	false	false	false	false
start_point_area	int			false	false	false				NULL								false	false	false	false	false	false
end_point_px	int			false	false	false				NULL								false	false	false	false	false	false
end_point_py	int			false	false	false				NULL								false	false	false	false	false	false
end_point_code	varchar	255		false	false	false				NULL				utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
end_point_angle	int			false	false	false				NULL								false	false	false	false	false	false
end_point_area	int			false	false	false				NULL								false	false	false	false	false	false
end_real_px	int			false	false	false				NULL								false	false	false	false	false	false
end_real_py	int			false	false	false				NULL								false	false	false	false	false	false
end_real_angle	int			false	false	false				NULL								false	false	false	false	false	false
odom_real	varchar	255		false	false	false				NULL	实际历程			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
odom_optimal	varchar	255		false	false	false				NULL	最优里程			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
```




```Markdown
名称	类型	长度	小数点	不是 Null	虚拟	键	虚拟类型	表达式	枚举值	默认值	注释	存储	列格式	字符集	排序规则	键长度	键排序	永远生成	根据当前时间戳更新	二进制	自动递增	无符号	填充零
id	int			true	false	true					主键id					0	ASC	false	false	false	true	false	false
from_system	varchar	50		false	false	false				NULL	来源系统			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
out_order_id	varchar	100		false	false	false				NULL	外部订单id			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
area_id	int			false	false	false				NULL	区域id							false	false	false	false	false	false
model_process_name	varchar	100		false	false	false				NULL	订单任务名称			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
model_process_id	int			false	false	false				NULL	拆分模式id							false	false	false	false	false	false
status	tinyint			false	false	false				NULL	订单状态1:未发送,2:正在取消,3:已取消,4:正在发送,5:发送失败,6:执行中,7:执行失败,8:任务完成,9:已下发							false	false	false	false	false	false
start_time	int			false	false	false				NULL	任务开始时间							false	false	false	false	false	false
station_name	varchar	64		false	false	false				NULL	点位名称			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
end_time	int			false	false	false				NULL	任务结束时间							false	false	false	false	false	false
create_time	int			false	false	false				NULL	任务创建时间							false	false	false	false	false	false
issue_time	int			false	false	false				NULL	任务延时后下发的时间点，时间戳							false	false	false	false	false	false
issue_delay	int			false	false	false				NULL	是否延时下发：0不延时，1延时下发							false	false	false	false	false	false
order_type	int			true	false	false				0	0:普通订单1：覆盖订单							false	false	false	false	false	false
is_support_agv	int			false	false	false				NULL	是否支持多车 默认多车 1单车 2多车							false	false	false	false	false	false
```


```Markdown
名称	类型	长度	小数点	不是 Null	虚拟	键	虚拟类型	表达式	枚举值	默认值	注释	存储	列格式	字符集	排序规则	键长度	键排序	永远生成	根据当前时间戳更新	二进制	自动递增	无符号	填充零
id	int			true	false	true										0	ASC	false	false	false	true	false	false
ics_task_order_id	int			false	false	false				NULL	任务id							false	false	false	false	false	false
model_process_id	int			false	false	false				NULL	拆分模式id							false	false	false	false	false	false
model_process_detail_id	int			false	false	false				NULL	拆分模式详情id							false	false	false	false	false	false
need_select_point	int			false	false	false				NULL	0不需要 ，1需要,2已选好							false	false	false	false	false	false
can_issue	int			false	false	false				NULL	任务下发状态：0不行 ，1可以下发任务,2已下发							false	false	false	false	false	false
task_template_name	varchar	100		false	false	false				NULL	子任务任务名称			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
task_template_id	int			false	false	false				NULL	任务流程子任务id							false	false	false	false	false	false
priority	int			false	false	false				NULL	子任务优先级:2:指定 4:高 6:中 8:低							false	false	false	false	false	false
task_type	tinyint			false	false	false				NULL	任务类型  1：RCS任务，2：机械臂任务，3：传送带任务							false	false	false	false	false	false
status	tinyint			false	false	false				NULL	任务状态1:未发送,2:正在取消,3:已取消,4:正在发送,5:发送失败,6:执行中,7:执行失败,8:任务完成,9:已下发							false	false	false	false	false	false
continue_status	tinyint			false	false	false				NULL	子任务状态，任务中才有：1等待确认状态							false	false	false	false	false	false
sub_task_status	tinyint			false	false	false				NULL	子任务状态，任务中才有：1等待确认状态							false	false	false	false	false	false
template_code	varchar	60		false	false	false				NULL	任务模板编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
task_path	varchar	512		false	false	false				NULL	任务路径			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
device_code	varchar	64		false	false	false				NULL	设备序列号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
device_num	varchar	64		false	false	false				NULL	设备编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
storage_num	varchar	64		false	false	false				NULL	库位，多个库位逗号分隔			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_number	varchar	32		false	false	false				NULL	货架编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
create_time	datetime			false	false	false				NULL	创建时间							false	false	false	false	false	false
start_time	datetime			false	false	false				NULL	开始时间							false	false	false	false	false	false
end_time	datetime			false	false	false				NULL	结束时间							false	false	false	false	false	false
material	varchar	1000		false	false	false				NULL	物料信息json			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
continue_condition_num	tinyint			false	false	false				NULL	继续任务条件数量							false	false	false	false	false	false
trigger_condition_num	tinyint			false	false	false				NULL	任务条件数量，有3个条件满足才会触发该任务，该值为3，减为0任务则下发。							false	false	false	false	false	false
action_param	varchar	200		false	false	false				NULL	action参数，如上料区高度、料箱宽度，json格式			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
current_station	varchar	64		false	false	false				NULL	任务当前位置			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
error_desc	varchar	200		false	false	false				NULL	任务失败原因			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
area_id	int			false	false	false				NULL	区域id							false	false	false	false	false	false
stacker_storage_num	int			false	false	false				NULL	堆高车放置的库位，1-5之间的数字							false	false	false	false	false	false
assign_robot_ids	varchar	64		false	false	false				NULL	指定设备延时处理下发的任务			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
carrier_type	int			false	false	false				NULL	载体类型: 0:货架 1:栈板 2:料箱 后续新增枚举							false	false	false	false	false	false
carrier_code	varchar	12		false	false	false				NULL	载体编号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
shelf_model	int			false	false	false				NULL	任务指定的负载型号，一般用于栈板型号指定							false	false	false	false	false	false
load_type	int			false	false	false				NULL	负载状态：一般用于指定设备背负的货架的类型是满、半满、空等							false	false	false	false	false	false
order_type	int			false	false	false				0	任务类型：0:普通任务1:覆盖任务2:关联任务							false	false	false	false	false	false
relateId	varchar	128		false	false	false				NULL	关联的任务单号			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
relate_id	int			false	false	false				NULL	任务关联id							false	false	false	false	false	false
notify_extra_status_id	varchar	50		false	false	false				NULL	额外状态配置id			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
release_robot	tinyint			false	false	false				NULL	0:释放  1:不释放  (默认释放)							false	false	false	false	false	false
had_trigger	tinyint			false	false	false				0	order_type为4-延时订单时，该任务是否已经触发过开始执行。0未触发过，1已经触发过							false	false	false	false	false	false
extend_field	varchar	255		false	false	false				NULL	扩展字段，格式：Json格式字符串。加入该字段的所有内容将会直接下发到TPS			utf8mb3	utf8mb3_general_ci			false	false	false	false	false	false
```


