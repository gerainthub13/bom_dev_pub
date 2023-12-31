# bom_ana

## name
暂时就是这个名字吧，还没有想好叫什么合适。

## purpose
两个目的：

1. 兑现一年前（2022-09）某日的想法。当初实现了比较“原始”的方案。作为一个python爱好者，需要用python完成一个版本，测试一下自己能力，是不是coder的材料。
2. 学习一下流行的app开发流程。与QT、TK的逻辑相比，基于web的开发会是怎样的一个体验？


## log
### 帐篷阶段(v 0.1-v0.3)
目前(20230819)推进到了0.3。相当于盖了个草棚子，或者是简易的帐篷。界面还比较原始，混合了Dash社区版的风格和部分Bootstrap风格的控件。但是基本的功能已经实现了。

#### 当前功能 v0.3
##### 基本设置
- 用户上传bom结构文件，包含BOM名称（bom_sn），BOM版本号（bom_version），用户标签名（user_tag，version结合tag可以支持同一个bom的不同版本，以及相同版本的不同价格形成的分支），层号（唯一键，需要严格遵守），部件编码，部件名称，数量，总数量
- 用户接入采购订单记录，工具自动计算平均价和最新价格。目前没有开放价格计算逻辑配置（可以改代码实现改配置）。
- 后台数据库理论上支持很广，目前开发测通了postgresql，预计SQL server的支持没有问题。
- app的运行需要至少一个py文件，依赖包主要是Dash、数据库驱动

##### 使用流程
1. 运行程序
2. 编辑bom模板，加入用户自己的bom清单
3. 拖入上传区。如果在模板中给出了bom_sn、bom_version、user_tag，app会自动填写。否则请手工填写这三项，非常重要。**不支持适用“_”（下划线）字符。**
4. 点击upload按钮后，app会将当前bom清单记录到bom_export表中，同时初始化一个显示版本。（* 有个小bug在此）
5. 手工价格编辑：手工价格列支持用户输入。双击数字，输入需要的数字，然后按“Enter”键确定。一定要确定。允许同时修改多个值。
6. 计算：点击计算按钮，给app一些时间，会自动重加载计算后的结果表。（2000行的bom，计算和加载时间预计在10S之内。与数据库、CPU主频、内存、价格计算逻辑相关）
7. 下载：点击下载按钮，可以将当前计算结果保存成本地Excel文件。
8. 多用户：理论上支持多用户同时操作。目前没有实现用户权限严格控制，建议多人适用的情况下，每个人只操作自己的user_tag
9. 采购价格：零件的采购价格没有区分项目！可能在下一个版本中开发，实际工作中，在采购订单层面标记项目版本很难实现标准化。建议通过手工价格实现项目间物料采购价格区分。可以通过后台数据库导入数据的方式，批量插入手工价格。可以通过修改更新时间戳到9999-12-31的方式，“固定”手工价格。

##### 逻辑流程
1. 上传bom后，录入bom_export表。这是设计之初的逻辑，后期会进行优化。保留这个逻辑的主要目的是变相记录用户操作，用于分析用户使用习惯、分析bom热度。
2. 上传bom后，会立即根据po价格计算一个bom cost表出来，这张表是支撑编辑和展示的核心。表名用“result_”+bom_sn+_+bom_version+_+user_tag组成，每次调用计算功能后，会生成新版本，同时删除旧版本。只保留最新运行的版本。按照目前采用的价格取数逻辑，会采用最新的PO价格和最新的手工价格。
3. 手工价格在点击计算按钮后追加到手工价格表。app会记录所有手工价格的变化，同时记录bom_sn、bom_version、user_tag，以保证多版本和隔离。方便后续价格对比相关功能的开发。
4. 目前如果想保留多个版本有两个方式：一，计算价格后，下载保存成本地excel文件；二，多次上传BOM，设定不同的user_tag。第一种方式会保留全部静态数据不再更新，第二种方式优势在于可以更新最新采购价格。**注意：即便有物料新的采购订单记录，如果不点击计算按钮，不会更新到最新采购价格**

### 打扫后的帐篷(v0.4_pg_done)
这个版本主要做代码治理：**v0.3可以作为测试版本使用**

- [X] 数据库连接配置集中化
- [X] 公共代码转function
- [X] 代码布局和注释优化
- [X] 模板下载

**PS:在对接sqlserver时，遇到了字符编码问题，正在排查，所以单独缓存了一个0.4，以防需要。**

### 对接SQLserver和pg双后端数据库 (v0.5)
折腾了一天，最终发现解决办法还是在一开始定位的情况：
SQL server的字符串类型和text类型是存在历史兼容设计的。使用varchar 或者text类型，不会像postgresql一样使用unicode编码。如果需要像postgres一样，提升对最新app的支持，**需要使用nvarchar类型。**
使用SQLalchemy操作SQL server时，主要是使用pandas 的to_sql（）功能时，或者提前定义好表字段数据类型为nvarchar，或者需要在to_sql（）中传递dtype（字典：{字段：SQLalchemy数据类型}），在dtypes中定义列使用nvarchar。
浪费的一天时间主要是因为没有通读sqlalchemy的文档，以为String类可以用，但实际上sqlalchemy有专门的NVARCHAR类型。
SQLalchemy 定义的数据类型和dialects存在对应的关系，见如下链接。
[Link, MSSQL 对应的数据类型](https://docs.sqlalchemy.org/en/13/dialects/mssql.html#sqlalchemy.dialects.mssql.NVARCHAR)

### 在Windows10 专业版 + SQL server 2022 单机环境下测试完成

在虚拟机环境中安装了Win10 和SQLserver 2022，没有找到方便下载的SQLserver 2012，但不会出问题了。可以准备推出去给人测试一下了。
发现了一个小问题，如果数据为空，前端datatable没有数据，所以会报错。
准备有时间了先处理一下。然后仔细规划一下后面的开发。


### 优化记录（v0.6）
#### 替换了不安全的全局变量
目前（v0.5）中使用了两个全局变量，一个用来同步数据库（不同数据库使用的sql和处理逻辑存在差异），一个用来缓存上传的bom数据（bom_uploaded）。
使用dcc.Store替换了 bom_uploaded，可以防止多用户操作上传时出现冲突。
**dccStore控件的位置需要足够明确，不能放在一开始加载还没有渲染的html代码部分！**

#### 使用offcanvas 替换sidebar

- 整体上，使用offcanvas替换了sidebar的设计，给bom展示留足了控件。
- 修正了一些界面上的交互bug，但还是不能保证异常交互的处理报错问题。 ！！
- Release版本在UI部分按钮添加“引导”性的描述。

### 优化记录 （v0.6R）
- 部分内容汉化
