# 简易安装说明（需要一些开发基础）

## 安装基础运行环境
由于小工具的设计结构很简单，并没有对运行环境做特定的要求。部署起来还是比较灵活的。

### 基本需求
#### python 环境
需要使用 python3 ，具体版本不定，在python 3.7， python 3.11上测试过。因为用到的功能都很基础，所以在版本选择上， 3.7-3.11都可以试一下。
同理因为没有用到版本特定的包，对于扩展包，推荐用pip上最新的稳定版就好。
可以使用官方的python安装程序，也可以使用anaconda。

#### 扩展包
需要的扩展包：
- pandas 数据分析和计算的基础
- sqlalchemy  数据库连接和管理
- pymssql  支撑SQL server的驱动库
- dash  APP 主要的framework
- psycopg2-binary Postgres驱动库
- dash-bootstrap-components  framework的bootstrap扩展，因为用了布局和按钮样式，所以需要安装。后期会因为app界面风格做调整。
- openpyxl 支持上传Excel（2003-365，xlsx扩展名）的解析。

~~~ bash
    pip isntall pandas sqlalchemy pymssql dash psycopg2-binary dash-bootstrap-components openpyxl
~~~

**安装前，需要在windows环境将python、pip加入环境变量！！！**
**建议更换国内的python源**

### 部署配置
#### 解包
工具主体就是一个python脚本文件，放置到方便管理的位置即可。运行产生的所有记录都在数据库中，不会产生本地缓存。

assets文件夹中存放了基本的CSS样式表，需要与app主脚本放在同一个目录。


#### 配置
配置工作分为两部分：
##### 一 数据库准备

对于postgres，选择一个库，创建schema “bom_dev”；对于sqlserver， 创建一个数据库 “bom_dev”。
并根据具体选用的数据库执行以下DDL语句。

**使用SQLserver时，需要指定数据库的Colation为“Chinese_PRC_CI_AS”**

~~~ SQL
/* for Postgresql*/
CREATE TABLE bom_dev.bom_export (
	bom_sn varchar(100) NOT NULL,
	bom_version varchar(100) NOT NULL,
	layer_sn varchar(100) NOT NULL,
	part_number varchar(100) NOT NULL,
	part_name varchar(100) NOT NULL,
	qty numeric(10, 2) NOT NULL,
	total_qty numeric(10, 2) NOT NULL,
	user_tag varchar(100) NULL,
	record_date varchar(100) NULL
);

CREATE TABLE bom_dev.manualprice (
	part_number varchar(100) NULL,
	part_name varchar(100) NULL,
	manualprice numeric(10, 2) NULL,
	bom_sn varchar(100) NULL,
	bom_version varchar(100) NULL,
	user_tag varchar(100) NULL,
	record_time varchar(100) NULL
);

CREATE TABLE bom_dev.po_history (
	po_number varchar(100) NULL,
	part_number varchar(100) NULL,
	part_name varchar(100) NULL,
	price numeric(10, 2) NULL,
	batch_qty numeric(10,2) NULL,
	po_date varchar(50) NULL
);

CREATE TABLE bom_dev.stdprice (
	part_number varchar(100) NULL,
	part_name varchar(100) NULL,
	stdprice numeric(10,2) NULL
);






/* for SQL Server*/
-- DEFAULT Colation is Chinese_PRC_CI_AS

CREATE TABLE bom_dev.dbo.bom_export (
	bom_sn nvarchar(100) NOT NULL,
	bom_version nvarchar(100) NOT NULL,
	layer_sn nvarchar(100) NOT NULL,
	part_number nvarchar(100) NOT NULL,
	part_name nvarchar(100) NOT NULL,
	qty numeric(10,2) NOT NULL,
	total_qty numeric(10,2) NOT NULL,
	user_tag nvarchar(100) NULL,
	record_date nvarchar(100) NULL
);

CREATE TABLE bom_dev.dbo.manualprice (
	part_number nvarchar(100) NULL,
	part_name nvarchar(100) NULL,
	manualprice numeric(10,2) NULL,
	bom_sn nvarchar(100) NULL,
	bom_version nvarchar(100) NULL,
	user_tag nvarchar(100) NULL,
	record_time nvarchar(100) NULL
);

CREATE TABLE bom_dev.dbo.po_history (
	po_number nvarchar(100) NULL,
	part_number nvarchar(100) NULL,
	part_name nvarchar(100) NULL,
	price numeric(10,2) NULL,
	batch_qty numeric(10,2) NULL,
	po_date nvarchar(50) NULL
);

CREATE TABLE bom_dev.dbo.stdprice (
	part_number nvarchar(100) NULL,
	part_name nvarchar(100) NULL,
	stdprice numeric(18,2) NULL
);

~~~

##### 二 脚本准备

在脚本的开头位置：
- 需要配置对应的数据库登录和连接信息；
- 需要根据数据库schema（postgres）或者数据库名（sqlserver）修正建立数据库链接的URL；
- 对于没有使用“bom_dev”名作为postgres schema的情况，需要搜索并更正所有to_sql()function中的schema名称；
- 修改脚本开头部分的访问地址和端口。


### 运行
定位到脚本所在目录，执行 python app_v0.5_R.py。

## PS：
数据库没有记录时，第一次上传bom清单会存在显示问题。关闭进程后重新打开可修复。
原因是界面加载逻辑没有考虑“无数据”状态时的显示场景，界面存在逻辑错误。已经着手修复中。