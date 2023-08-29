from dash import Dash, html, dash_table, dcc, callback, Output, Input, State
import pandas as pd
import numpy as np
import plotly.express as px
import dash_bootstrap_components as dbc
import sqlalchemy
import datetime
import time
import base64, io
import uuid

from sqlalchemy import String, Integer, Float, Numeric, NVARCHAR

###########################################################################################
#      Configurations
###########################################################################################
## Use either one is OK.
# --------------------------------------------------------------------------
# rdbms = 'postgres'
rdbms = "sqlserver"

# --------------------------------------------------------------------------

debug = True
jupyter_mode = "external"
host = "0.0.0.0"
port = 8050
jupyter_server_url = "192.168.88.251:8050"

###########################################################################################
#      global varibles
###########################################################################################

# bom_uploaded = ''  ## placeholder for a a varible.  replaced with dcc.store since v0.5
template_columns = [
    "bom_sn",
    "bom_version",
    "user_tag",
    "layer_sn",
    "part_number",
    "part_name",
    "qty",
    "total_qty",
]


###########################################################################################
#      Functions
###########################################################################################


def connect_2_db():
    global rdbms
    if rdbms == "postgres":
        return sqlalchemy.create_engine(
            "postgresql://postgres:postgres@192.168.88.251/demo_data", echo=False
        )
    if rdbms == "sqlserver":
        return sqlalchemy.create_engine(
            "mssql+pymssql://sa:myStrongP_sw@192.168.88.251/bom_dev?charset=utf8",
            echo=False,
        )
        # return pymssql()


def get_bom_list():
    global rdbms
    ## load bom export table from database table
    ## instead of load bom list from "bom_export", we use table name pattern, "pg_class" and "pg_catalog"
    conn = connect_2_db()
    if rdbms == "postgres":
        query = """
        select
        	--split_part(c.relname,'_',1) as table_type,
        	split_part(c.relname,'_',2) as bom_sn,
        	split_part(c.relname,'_',3) as bom_version,
        	split_part(c.relname,'_',4) as user_tag
        from
        	pg_catalog.pg_class c
        join pg_catalog.pg_namespace n on
        	c.relnamespace = n."oid"
        where
        	n.nspname = 'bom_dev'
        	and split_part(c.relname,'_',1) = 'result'
        order by c."relname" desc
        """
        df_bom_list = pd.read_sql(sqlalchemy.text(query), con=conn)
        conn.dispose()
        # df_bom_list.rename(columns = {'bom_sn':'BOM Name','bom_version':'Version',"user_tag":'User Tag'}, inplace = True)

    if rdbms == "sqlserver":
        query = """
                SELECT 
                TABLE_NAME as tablename
                FROM INFORMATION_SCHEMA.TABLES
                where TABLE_CATALOG = 'bom_dev'
                and TABLE_NAME like 'result%';
        """
        df = pd.read_sql(sqlalchemy.text(query), con=conn)
        conn.dispose()
        dic_df = df.to_dict("records")
        dic_newdf = []
        for d in dic_df:
            s = d["tablename"].split("_")
            dic_newdf.append(
                {
                    "bom_sn": s[1],
                    "bom_name": s[2],
                    "user_tag": s[3],
                }
            )
        df_bom_list = pd.DataFrame(dic_newdf)
        # df_bom_list.rename(columns = {'bom_sn':'BOM Name','bom_version':'Version',"user_tag":'User Tag'}, inplace = True)

    # print("df_bom_list--:",df_bom_list)
    # print(len(df_bom_list))
    if len(df_bom_list) > 0:
        return df_bom_list
    else:
        return pd.DataFrame([{"id": "1", "info": "Please update a BOM file."}])
    ############################################################## 这里需要优化以下，如何输出bom_list是空的情况。


def get_original_bom(bom_sn, bom_version, user_tag):
    global rdbms
    conn = connect_2_db()
    tablename = "_".join(["result", bom_sn, bom_version, user_tag])
    if rdbms == "postgres":
        query = """
        SELECT bom_sn,bom_version,user_tag,layer_sn,part_number,part_name,qty,total_qty,layer_level,manually_set_price,latest_po_price,price,updatetime
        FROM "bom_dev"."####tablename&&&&"
        """
    if rdbms == "sqlserver":
        query = """
        SELECT bom_sn,bom_version,user_tag,layer_sn,part_number,part_name ,qty,total_qty,layer_level,manually_set_price,latest_po_price,price,updatetime
        FROM "bom_dev"."dbo".[####tablename&&&&]
        """
    # query += " where bom_sn = '" + str(bom_sn) + "' and bom_version ='" + str(bom_version) + "' and user_tag = '"+user_tag+"' "
    query += "order by layer_sn ;"
    query = query.replace("####tablename&&&&", tablename)
    # print(query)
    df = pd.read_sql(sqlalchemy.text(query), con=conn)
    # print(df.to_dict('records'))
    conn.dispose()
    return df


###############################################
## 这是一个超级长的处理
# 包括：
# 读取bom清单、读取PO、标准价、手工价，
# 计算PO价，计算PO均价
# 根据价格源，计算成本
# 输出结果到数据库。
## 这里的逻辑还不是非常清晰，需要仔细计划一下。
###############################################
def calculate_bom(bom_sn, bom_version, user_tag):
    ## 输出 + updatetime
    global rdbms
    df_bom = get_original_bom(bom_sn, bom_version, user_tag)
    # print('-- read from table scructure (df_bom) :--\n',df_bom)
    conn = connect_2_db()
    # ===================================================================
    ## 获取PO latest
    if rdbms == "postgres":
        query = """
        with sorted as (
        select
            po_number,part_number,part_name,price,batch_qty,po_date,row_number() over( partition by part_number order by po_date desc) as s 
        from
            "bom_dev".po_history p
        )
        select po_number,part_number,part_name,price,batch_qty,po_date
        from sorted where s = 1;
        """
    if rdbms == "sqlserver":
        query = """
        with sorted as (
        select
            po_number,part_number,part_name,price,batch_qty,po_date,row_number() over( partition by part_number order by po_date desc) as s 
        from
            "bom_dev"."dbo".po_history p
        )
        select po_number,part_number,part_name,price,batch_qty,po_date
        from sorted where s = 1;
        """

    df_po_latest = pd.read_sql(sqlalchemy.text(query), con=conn)
    # ===================================================================
    ## 获取PO avg
    tablename = "po_history"
    if rdbms == "postgres":
        query = """
        with totalamount as (
        select
            part_number,part_name,sum(price*batch_qty)as amount
        from
            "bom_dev".po_history p
        group by 
        part_number,part_name
        ),
        totalqty as (
        select
            part_number,part_name,sum(batch_qty) as tqty
        from
            "bom_dev".po_history p
        group by 
        part_number,part_name
        )
        select a.part_number,a.part_name, (a.amount/q.tqty)::numeric(10,2) as avgpoprice 
        from totalamount a
        join totalqty q on a.part_number=q.part_number and a.part_name=q.part_name
        """
    if rdbms == "sqlserver":
        query = """
        with totalamount as (
        select
            part_number,part_name,sum(price*batch_qty)as amount
        from
            "bom_dev"."dbo".po_history p
        group by 
        part_number,part_name
        ),
        totalqty as (
        select
            part_number,part_name,sum(batch_qty) as tqty
        from
            "bom_dev"."dbo".po_history p
        group by 
        part_number,part_name
        )
        select a.part_number,a.part_name, cast((a.amount/q.tqty) as numeric(10,2)) as avgpoprice 
        from totalamount a
        join totalqty q on a.part_number=q.part_number and a.part_name=q.part_name
        """
    query = query.replace("####tablename&&&&", tablename)
    df_po_avg = pd.read_sql(sqlalchemy.text(query), con=conn)
    # ===================================================================
    ## 获取std_price
    tablename = "stdprice"
    if rdbms == "postgres":
        query = """
        SELECT x.* FROM "bom_dev".####tablename&&&& x;
        """
    if rdbms == "sqlserver":
        query = """
        SELECT x.* FROM "bom_dev".dbo.[####tablename&&&&] x;
        """
    query = query.replace("####tablename&&&&", tablename)
    df_stdp = pd.read_sql(sqlalchemy.text(query), con=conn)
    # ===================================================================
    ## 获取手工价格
    if rdbms == "postgres":
        query = """
            with sorted as (
            select row_number()over(partition by part_number,bom_sn,bom_version,user_tag order by record_time desc) as rn, * from "bom_dev".manualprice mn 
            filter_place_holder
            )
            select * from sorted where rn = 1 ;
            """
    if rdbms == "sqlserver":
        query = """
            with sorted as (
            select row_number()over(partition by part_number,bom_sn,bom_version,user_tag order by record_time desc) as rn, * from "bom_dev"."dbo".manualprice mn 
            filter_place_holder
            )
            select * from sorted where rn = 1 ;
            """
    filter_sql = (
        " where bom_sn = '"
        + bom_sn
        + "' and bom_version = '"
        + bom_version
        + "' and user_tag  = '"
        + user_tag
        + "' "
    )
    query = query.replace("filter_place_holder", filter_sql)
    df_mp = pd.read_sql(sqlalchemy.text(query), con=conn)
    conn.dispose()
    ## 获取所有层号的列表，全集。
    # all part_numbers
    all_layer_sn = []
    for p in df_bom["layer_sn"].unique():
        all_layer_sn.append(p.split("."))

    ## 基础数据计算处理
    bomdata = {}
    # convert pandas data to structure
    ### 在比较层码时，使用了list比较，而不是字符串比较。 ！！！
    for i in df_bom[
        [
            "bom_sn",
            "bom_version",
            "layer_sn",
            "part_number",
            "part_name",
            "qty",
            "total_qty",
            "user_tag",
        ]
    ].to_records(dict):
        ## 数据认领
        is_root = True
        has_bom = False
        current_layer_sn = i[3].split(".")
        part_number = i[4]
        part_name = i[5]
        bom_sn = i[1]
        bom_version = i[2]
        qty = i[6]
        total_qty = i[7]
        # user_tag=i[8]

        ## 判断是否含有子集层
        for compare_to in all_layer_sn:
            # print(compare_to)
            if len(compare_to) > len(current_layer_sn):
                if compare_to[: len(current_layer_sn)] == current_layer_sn:
                    has_bom = True
                    break

        ## 判断是否是root层
        for compare_to in all_layer_sn:
            if compare_to[: len(current_layer_sn)] != current_layer_sn:
                is_root = False
                break

        ## 识别父级
        parent = ""
        if not is_root:
            parent = current_layer_sn[: len(current_layer_sn) - 1]

        ## 识别子级
        children = []
        if has_bom:
            children = []
            for compare_to in all_layer_sn:
                if compare_to[:-1] == current_layer_sn:
                    children.append(".".join(compare_to))

        ## 数据结构输出
        bomdata[i[3]] = {
            "layer_sn": current_layer_sn,
            "layer_symbol": ".",
            "layer_level": len(current_layer_sn),
            "part_number": part_number,
            "part_name": part_name,
            "bom_sn": bom_sn,  ## 暂时没有考虑一个物料的多个bom版本问题，扩充相对而言比较容易，需要数据辅助演示.
            "bom_version": bom_version,
            "qty": qty,
            "total_qty": total_qty,
            ## Use -1 to identify there is no such records. cost1~cost4 is for "price", other 4 prices just for reff.
            "manually_set_price": -1,  # opt3
            "latest_po_price": -1,  # opt1
            "avg_po_price": -1,  # opt2
            "std_price": -1,  # opt4
            "price": -1,
            "price_source": 3,  ## one of the above 4 options. if -1 then calculated price (ommit -1 childrens).
            "is_root": is_root,
            "has_bom": has_bom,
            "parent": parent,
            "children": children,
        }

    ##debug bomdata (type of dic)
    # print('--bomdata--(genereating check)\n',bomdata)
    ## 所有的物料都可能会有4个价格，不需要区分是否含有bom。
    def calLatestPoPrice(part_number, part_name):  ## 1.最近PO价格（最近PO价格 > 0）
        if (
            len(
                df_po_latest[
                    (df_po_latest["part_number"] == part_number)
                    & (df_po_latest["part_name"] == part_name)
                ]["price"]
            )
            == 1
        ):
            p = df_po_latest[
                (df_po_latest["part_number"] == part_number)
                & (df_po_latest["part_name"] == part_name)
            ]["price"].tolist()[0]
        else:
            p = -1
        return p

    def calAvgPoPrice(part_number, part_name):  ## 2.平均PO价格（平均PO价格 >  0）
        if (
            len(
                df_po_avg[
                    (df_po_avg["part_number"] == part_number)
                    & (df_po_avg["part_name"] == part_name)
                ]["avgpoprice"]
            )
            == 1
        ):
            p = df_po_avg[
                (df_po_avg["part_number"] == part_number)
                & (df_po_avg["part_name"] == part_name)
            ]["avgpoprice"].tolist()[0]
        else:
            p = -1
        return p

    def calManuallySetPrice(part_number, part_name):  ## 3.调整价格（手工价格 > 0）  *default
        if (
            len(
                df_mp[
                    (df_mp["part_number"] == part_number)
                    & (df_mp["part_name"] == part_name)
                ]["manualprice"]
            )
            == 1
        ):
            p = df_mp[
                (df_mp["part_number"] == part_number)
                & (df_mp["part_name"] == part_name)
            ]["manualprice"].tolist()[0]
        else:
            p = -1
        return p

    def calStdPrice(part_number, part_name):  ## 4.保底（标准价格 > 0）
        if (
            len(
                df_stdp[
                    (df_stdp["part_number"] == part_number)
                    & (df_stdp["part_name"] == part_name)
                ]["stdprice"]
            )
            == 1
        ):
            p = df_stdp[
                (df_stdp["part_number"] == part_number)
                & (df_stdp["part_name"] == part_name)
            ]["stdprice"].tolist()[0]
        else:
            p = -1
        return p

    ## 计算组件的cost/price
    for layerSn in bomdata.keys():
        bomdata[layerSn]["latest_po_price"] = calLatestPoPrice(
            bomdata[layerSn]["part_number"], bomdata[layerSn]["part_name"]
        )
        bomdata[layerSn]["avg_po_price"] = calAvgPoPrice(
            bomdata[layerSn]["part_number"], bomdata[layerSn]["part_name"]
        )
        bomdata[layerSn]["manually_set_price"] = calManuallySetPrice(
            bomdata[layerSn]["part_number"], bomdata[layerSn]["part_name"]
        )
        bomdata[layerSn]["std_price"] = calStdPrice(
            bomdata[layerSn]["part_number"], bomdata[layerSn]["part_name"]
        )

    # print(bomdata)
    ## 计算组件的cost/price, Loop enough times...

    ## price_source计算逻辑 ：
    ## 1.最近PO价格（最近PO价格 > 层级计算 > 0）
    ## 2.平均PO价格（平均PO价格 > 标准价格 > 层级计算 > 0）
    ## 3.调整价格（最近PO价格 > 手工价格 > 层级计算 > 0）  *default
    ## 4.保底（平均PO价格 > 标准价格 > 手工价格 > 层级计算 > 0）
    def firstNotM1(listOfPrices):
        gotValidPrice = False
        for l in listOfPrices:
            if float(l) >= 0:
                gotValidPrice = True
                break
        if gotValidPrice:
            return l
        else:
            return -1

    def calLayers(layerSn):
        p = 0
        for c in bomdata[layerSn]["children"]:
            if bomdata[c]["price"] != -1:
                p += bomdata[c]["price"] * bomdata[c]["qty"]  ## 汇算价格时乘以数量。
        return p

    ## 计算组件的cost/price
    ## 目前的逻辑决定了，不管有没有子层级bom，po价格、手工价格都要取到。在此做个判断预留，防止日后需要复杂逻辑调整。
    for layerSn in bomdata.keys():
        # print(bomdata[layerSn]['has_bom'])
        if bomdata[layerSn]["has_bom"] == False:  # Base part
            if bomdata[layerSn]["price_source"] == 1:
                bomdata[layerSn]["price"] = firstNotM1(
                    [bomdata[layerSn]["latest_po_price"]]
                )
            if bomdata[layerSn]["price_source"] == 2:
                bomdata[layerSn]["price"] = firstNotM1(
                    [bomdata[layerSn]["avg_po_price"], bomdata[layerSn]["std_price"]]
                )
            if bomdata[layerSn]["price_source"] == 3:
                bomdata[layerSn]["price"] = firstNotM1(
                    [
                        bomdata[layerSn]["manually_set_price"],
                        bomdata[layerSn]["latest_po_price"],
                    ]
                )
            if bomdata[layerSn]["price_source"] == 4:
                bomdata[layerSn]["price"] = firstNotM1(
                    [
                        bomdata[layerSn]["manually_set_price"],
                        bomdata[layerSn]["avg_po_price"],
                        bomdata[layerSn]["std_price"],
                    ]
                )
        if bomdata[layerSn]["has_bom"] == True:  # part that with both bom and po_price
            if bomdata[layerSn]["price_source"] == 1:
                bomdata[layerSn]["price"] = firstNotM1(
                    [bomdata[layerSn]["latest_po_price"]]
                )
            if bomdata[layerSn]["price_source"] == 2:
                bomdata[layerSn]["price"] = firstNotM1(
                    [bomdata[layerSn]["avg_po_price"], bomdata[layerSn]["std_price"]]
                )
            if bomdata[layerSn]["price_source"] == 3:
                bomdata[layerSn]["price"] = firstNotM1(
                    [
                        bomdata[layerSn]["manually_set_price"],
                        bomdata[layerSn]["latest_po_price"],
                    ]
                )
            if bomdata[layerSn]["price_source"] == 4:
                bomdata[layerSn]["price"] = firstNotM1(
                    [
                        bomdata[layerSn]["manually_set_price"],
                        bomdata[layerSn]["avg_po_price"],
                        bomdata[layerSn]["std_price"],
                    ]
                )
    l = [i for i in range(0, 30)]
    l.reverse()
    for layer_counter in l:
        # print(layer_counter)
        for layerSn in bomdata.keys():
            if bomdata[layerSn]["layer_level"] == layer_counter:
                bomdata[layerSn]["price"] = firstNotM1(
                    [bomdata[layerSn]["price"], calLayers(layerSn)]
                )  ## Use manually price before PO
    # print(bomdata)
    ## Convert to dataframe, then upload to database.
    output = []
    l = list(bomdata.keys())
    for i in l:
        output.append(
            {
                "layer_sn": i,
                "layer_level": bomdata[i]["layer_level"],
                "part_number": bomdata[i]["part_number"],
                "part_name": bomdata[i]["part_name"],
                "bom_sn": bomdata[i]["bom_sn"],
                "bom_version": bomdata[i]["bom_version"],
                "qty": bomdata[i]["qty"],
                "total_qty": bomdata[i]["total_qty"],
                "manually_set_price": bomdata[i]["manually_set_price"],
                "latest_po_price": bomdata[i]["latest_po_price"],
                "avg_po_price": bomdata[i]["avg_po_price"],
                "std_price": bomdata[i]["std_price"],
                "price": bomdata[i]["price"],
                "price_source": bomdata[i]["price_source"],
                "is_root": bomdata[i]["is_root"],
                "has_bom": bomdata[i]["has_bom"],
                "user_tag": user_tag,
                "updatetime": str(datetime.datetime.today())[:19],
            }
        )
    df_out = pd.DataFrame(output)
    dtp = {
        "layer_sn": NVARCHAR(100),
        "layer_level": NVARCHAR(100),
        "part_number": NVARCHAR(100),
        "part_name": NVARCHAR(100),
        "bom_sn": NVARCHAR(100),
        "bom_version": NVARCHAR(100),
        "qty": Float(),
        "total_qty": Float(),
        "manually_set_price": Float(),
        "latest_po_price": Float(),
        "avg_po_price": Float(),
        "std_price": Float(),
        "price": Float(),
        "price_source": Integer(),
        "user_tag": NVARCHAR(100),
        "updatetime": NVARCHAR(50),
    }
    # print(df_out)
    conn = connect_2_db()
    write_to_table = "_".join(["result", bom_sn, bom_version, user_tag])
    if rdbms == "postgres":
        df_out.to_sql(
            write_to_table, con=conn, schema="bom_dev", if_exists="replace", index=False
        )
    if rdbms == "sqlserver":
        df_out.to_sql(
            write_to_table, con=conn, if_exists="replace", dtype=dtp, index=False
        )
    conn.dispose()
    print("calculating")


###########################################################################################
#      Initialize the app
###########################################################################################

app = Dash(
    __name__, suppress_callback_exceptions=True
)  ## searched the net, and found this opt to supress ID not found warning.  "suppress_callback_exceptions=True"

###########################################################################################
#      Contents, part on right side of page
###########################################################################################
# the styles for the main content position it to the right of the sidebar and
# add some padding.

## bom select window
select_bom = html.Div(
    html.Div(
        [
            html.H5("从列表中选择需要分析的BOM清单."),
            html.Div(
                [
                    dash_table.DataTable(
                        id="bom-table",
                        data=get_bom_list().to_dict("records"),
                        columns=[{"name": i, "id": i} for i in get_bom_list().columns],
                        page_size=5,
                        editable=False,
                        row_selectable="single",
                        sort_action="native",
                        sort_mode="multi",
                        filter_action="native",
                        selected_rows=[0],  # default : the first line.
                    ),
                ],
                id="div-bom-table",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Button(
                            "刷新列表",
                            id="button-refresh-bom-list",
                            color="primary",
                            n_clicks=0,
                        ),
                        width=2,
                    ),
                    dbc.Col(
                        dbc.Button(
                            "加载", id="button-select-bom", color="success", n_clicks=0
                        ),
                        width=2,
                    ),
                ],
                className="mt-3",
                justify="end",
            ),
        ]
    )
)
## upload control
upload_funcs = html.Div(
    [
        html.Div(
            [
                html.Hr(),
                html.H5("使用Excel(.xlsx)文件格式上传BOM."),
                html.P("点击'Get Template' 按钮，下载bom清单模板. "),
                html.P(
                    "上传bom清单后，还是可以修改录入的 bom_sn, bom_name and user_tag 信息。目的在于方便上传一份BOM，形成多个计算版本。"
                ),
                dbc.Label("BOM Name(bom_sn):"),
                dbc.Input(
                    id="input-bom-name", placeholder="Part Number of a BOM", type="text"
                ),
                dbc.Label("Version(bom_version)"),
                dbc.Input(
                    id="input-bom-version",
                    placeholder="Version Number of a BOM",
                    type="text",
                ),
                dbc.Label("User Tag(user_tag)"),
                dbc.Input(
                    id="input-user-tag", placeholder="Who owns this", type="text"
                ),
                html.Div(
                    [
                        dcc.Upload(
                            id="upload-file",
                            children=html.Div(
                                ["鼠标拖拽文件到此，或者 ", html.A("选择一个文件."), "(xlsx files only)"]
                            ),
                            style={
                                "width": "100%",
                                "height": "50px",
                                "lineHeight": "50px",
                                "borderWidth": "1px",
                                "borderStyle": "dashed",
                                "borderRadius": "5px",
                                "textAlign": "center",
                                "margin": "10px",
                            },
                            multiple=False,  # Could allow multiple files to be uploaded. But no need here.
                        ),
                        html.Div(
                            "请使用模板. ",
                            id="output-file-process-comments",
                            style={"color": "Red"},
                        ),
                    ]
                ),
                html.Button("Get Template", id="button-download-template", n_clicks=0),
                dbc.Button(
                    "上传文件",
                    id="button-upload-submit",
                    disabled=True,
                    color="success",
                    className="me-2",
                    n_clicks=0,
                ),
                dcc.Download(id="download-template"),
            ]
        )
    ]
)
content = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.H2("BOM 成本计算器", className="display-5"),
                        html.P("一个用于分析BOM清单采购成本的简单工具（演示版本）."),
                    ]
                ),
                dbc.Col(
                    dbc.Button("1. 选择一个BOM", id="open-side-bar", n_clicks=0), width=2
                ),
                dbc.Col(
                    dbc.Button(
                        "2. 计算成本",
                        id="button-calculate-bom-price",
                        color="primary",
                        n_clicks=0,
                    ),
                    width=2
                    # html.Button("Calculate", id="button-calculate-bom-price", n_clicks=0),  ## try Dash button style
                ),
                dbc.Col(
                    dbc.Button(
                        "3. 导出结果", id="button-download-bom", color="success", n_clicks=0
                    ),
                    width=2,
                ),
                dcc.Download(
                    id="download-dataframe-xlsx"
                ),  ## Have to use this?? It seams so...
                dcc.Store(id="store-uploaded-bom"),
                dbc.Offcanvas(
                    [
                        html.H2("BOM 成本计算器", className="display-5"),
                        html.P("一个用于分析BOM清单采购成本的简单工具（演示版本）."),
                        select_bom,
                        upload_funcs,
                    ],
                    className="lead",
                    id="side-bar",
                    # title="BOM Cost Calculator",
                    style={
                        "top": 0,
                        "left": 0,
                        "bottom": 0,
                        "width": "60rem",
                        "padding": "2rem 1rem",
                        "background-color": "#f8f9fa",
                    },
                    is_open=False,
                ),
            ],
            className="mt-3",
            justify="end",
        ),
        html.Div("", style={"height": "1em"}),
        html.Div(
            html.Div(
                [
                    dash_table.DataTable(
                        id="bom-edit-view",
                        # data=[{'layer_sn':'', 'layer_level':'', 'part_number':'', 'part_name':'', 'qty':'',
                        #       'total_qty':'', 'manually_set_price':'', 'latest_po_price':'', 'price':'', 'updatetime':'','id':'1'}],
                        data=[{"info": "请先选择一个BOM清单记录"}],
                    )
                ]
            ),
            id="bom-content",
        ),
    ],
    id="page-content",
    style={
        "margin-left": "2rem",
        "margin-right": "2rem",
        "padding": "2rem 1rem",
    },
)

###########################################################################################
#      Layout
###########################################################################################

app.layout = html.Div(
    [
        dcc.Location(id="url"),
        # sidebar,
        content,
    ]
)


###########################################################################################
#      Callbacks
###########################################################################################
##  Upload process step1: upload file and check.
@callback(
    Output("output-file-process-comments", "children"),
    Output("input-bom-name", "value"),
    Output("input-bom-version", "value"),
    Output("input-user-tag", "value"),
    Output("store-uploaded-bom", "data"),
    Output("button-upload-submit", "disabled"),
    Input("upload-file", "contents"),
    State("upload-file", "filename"),
    State("upload-file", "last_modified"),
    prevent_initial_call=True,
)
def update_check(file_content, file_name, modified_date):
    # global bom_uploaded
    # bom_uploaded = ''
    random_id = str(uuid.uuid1())
    bom_sn = "No_bom_name_in_file"
    bom_version = "No_bom_version_in_file"
    user_tag = random_id
    # print('work?')
    file_check_comments = "No file uploaded. OR not validated file."
    if file_content is None:
        return (
            file_check_comments,
            "Part Number of BOM",
            "Versioin of BOM",
            "Your tag to identify this bom.",
            "",
            True,
        )
    else:
        content_type, content_string = file_content.split(",")
        decoded = base64.b64decode(content_string)
        # print(decoded)
        try:
            if "xlsx" in file_name.lower():
                df = pd.read_excel(io.BytesIO(decoded))
            else:
                file_check_comments = "ERROR: Not an xlsx file!"
            for c in df.columns:
                if c not in template_columns:
                    file_check_comments = "ERROR: Please use template file!"
                    break
            ## extract bom_sn bom_version user_tag
            if "bom_sn" in df.columns:
                bom_sn = df["bom_sn"].loc[0]
            if "bom_version" in df.columns:
                bom_version = df["bom_version"].loc[0]
            if "user_tag" in df.columns:
                user_tag = df["user_tag"].loc[0]
            ## if everything is OK...
            # bom_uploaded = df
            file_check_comments = 'BOM file loaded, click "Upload" Button to process.'

        except Exception as e:
            print(e)
            return (
                file_check_comments,
                "Part Number of BOM",
                "Versioin of BOM",
                "Your tag to identify this bom.",
                False,
            )
        return (
            file_check_comments,
            bom_sn,
            bom_version,
            user_tag,
            df.to_dict("records"),
            False,
        )


##  Upload process step2: insert bom to bom_export table and call the iniative calculation of Price.
@callback(
    Output("bom-table", "data", allow_duplicate=True),
    Input("button-upload-submit", "n_clicks"),
    State("input-bom-name", "value"),
    State("input-bom-version", "value"),
    State("input-user-tag", "value"),
    State("store-uploaded-bom", "data"),
    prevent_initial_call=True,
)
def add_records_and_refresh(nc, bom_sn, bom_version, user_tag, df):
    global rdbms
    # global bom_uploaded
    bom_uploaded = pd.DataFrame(df)
    # print("---bom-table---\n",bom_uploaded)
    if len(bom_uploaded) > 0:
        if len(bom_uploaded) > 1 and type(bom_uploaded) == pd.DataFrame:
            # print("is df.")
            to_replace = []
            for b in bom_uploaded.to_dict("records"):
                to_replace.append(
                    {
                        "bom_sn": bom_sn,
                        "bom_version": bom_version,
                        "user_tag": user_tag,
                        "layer_sn": b["layer_sn"],
                        "part_number": b["part_number"],
                        "part_name": b["part_name"],
                        "qty": b["qty"],
                        "total_qty": b["total_qty"],
                        "layer_level": 0,
                        "manually_set_price": -1,
                        "latest_po_price": -1,
                        "price": -1,
                        "updatetime": "",
                    }
                )
        dtp = {
            "layer_sn": NVARCHAR(100),
            "layer_level": Integer(),
            "part_number": NVARCHAR(100),
            "part_name": NVARCHAR(100),
            "bom_sn": NVARCHAR(100),
            "bom_version": NVARCHAR(100),
            "qty": Float(),
            "total_qty": Float(),
            "manually_set_price": Float(),
            "latest_po_price": Float(),
            "price": Float(),
            "user_tag": NVARCHAR(100),
            "updatetime": NVARCHAR(50),
        }
        conn = connect_2_db()
        df_out = pd.DataFrame(to_replace)
        # print("add_records_and_refresh  -----   ",df_out)
        ## create table for each combination.
        write_to_table = "_".join(["result", bom_sn, bom_version, user_tag])
        # print('----write_to_table:----(first write to)\n',write_to_table)
        # print(write_to_table)
        if rdbms == "postgres":
            df_out.to_sql(
                "_".join(["result", bom_sn, bom_version, user_tag]),
                con=conn,
                schema="bom_dev",
                if_exists="replace",
                index=False,
            )
        if rdbms == "sqlserver":
            df_out.to_sql(
                write_to_table, con=conn, if_exists="replace", dtype=dtp, index=False
            )
        df_out["record_date"] = str(datetime.datetime.today())[:19]

        ## insert records to bom_export
        if rdbms == "postgres":
            df_out[
                [
                    "bom_sn",
                    "bom_version",
                    "layer_sn",
                    "part_number",
                    "part_name",
                    "qty",
                    "total_qty",
                    "user_tag",
                    "record_date",
                ]
            ].to_sql(
                "bom_export",
                con=conn,
                schema="bom_dev",
                if_exists="append",
                index=False,
            )
        if rdbms == "sqlserver":
            df_out[
                [
                    "bom_sn",
                    "bom_version",
                    "layer_sn",
                    "part_number",
                    "part_name",
                    "qty",
                    "total_qty",
                    "user_tag",
                    "record_date",
                ]
            ].to_sql("bom_export", con=conn, if_exists="append", index=False)
        conn.dispose()
        # print('-- from upload_button: --', '_'.join(['result',bom_sn,bom_version,user_tag]))
        ## calculate price and cost
        calculate_bom(bom_sn, bom_version, user_tag)
        ## Refesh bom table
        df_bom_list = get_bom_list()
        return df_bom_list.to_dict("records")
    else:
        return [{"id": "1", "info": "Please choose or upload a bom file first."}]


## Refesh bom table - refrash
@callback(
    Output("div-bom-table", "children"),
    Output("button-select-bom", "disabled", allow_duplicate=True),
    Input("button-refresh-bom-list", "n_clicks"),
    prevent_initial_call=True,
)
def update_bom_table(n):
    df_bom_list = get_bom_list()
    # print('why not refresh??',df_bom_list.to_dict('records'))
    output_table = dash_table.DataTable(
        id="bom-table",
        data=df_bom_list.to_dict("records"),
        # data= [{'bom_sn':'0',"bom_version":'0',"user_tag":'0', "id":'0'}],
        columns=[{"name": i, "id": i} for i in df_bom_list.columns],
        page_size=5,
        editable=False,
        row_selectable="single",
        sort_action="native",
        sort_mode="multi",
        filter_action="native",
        selected_rows=[0],  # default : the first line.
    )
    if "info" in df_bom_list.columns:
        return (output_table, True)
    else:
        return (output_table, False)


## load selected bom line to content on the right - select
@callback(
    Output("bom-content", "children"),
    Input("button-select-bom", "n_clicks"),
    State("bom-table", "selected_rows"),
    prevent_initial_call=True,
)
def load_bom_table(n, sr):
    df_bom_list = get_bom_list()
    bom_sn = df_bom_list.loc[sr[0]].tolist()[0]
    bom_version = df_bom_list.loc[sr[0]].tolist()[1]
    user_tag = df_bom_list.loc[sr[0]].tolist()[2]
    df_bom_edit = get_original_bom(bom_sn, bom_version, user_tag)
    # print(df_bom_edit)
    if "info" not in get_bom_list().columns:
        # print("df_bom_list to show:\n",df_bom_list)
        # print("df_bom_edit\n",df_bom_edit)

        column_setting = []
        df_bom_edit_filtered = df_bom_edit[
            [
                "layer_sn",
                "layer_level",
                "part_number",
                "part_name",
                "qty",
                "total_qty",
                "manually_set_price",
                "latest_po_price",
                "price",
                "updatetime",
            ]
        ]
        editable_columns = ["manually_set_price"]
        for col in df_bom_edit_filtered.columns:
            if col in editable_columns:
                column_setting.append(
                    {
                        "editable": True,
                        "name": col,
                        "id": col,
                    }
                )
            else:
                column_setting.append(
                    {
                        "editable": False,
                        "name": col,
                        "id": col,
                    }
                )
        # print(column_setting)
        return html.Div(
            [
                dash_table.DataTable(
                    id="bom-edit-view",
                    data=df_bom_edit_filtered.to_dict("records"),
                    columns=column_setting,
                    page_size=25,
                    editable=False,
                    # row_selectable="single", # no need of selection.
                    sort_action="native",
                    sort_mode="multi",
                    filter_action="native",
                    # selected_rows=[0] # default the forst one.
                ),
            ]
        )
    else:
        return html.Div("Please choose or upload a bom file first.")


## CALCULATE button
## 1. analyse changed lines, insert new manual price to manualprice table
## 2. re-caculate the cost


@callback(
    Output("bom-edit-view", "data"),
    Input("button-calculate-bom-price", "n_clicks"),
    [State("bom-table", "selected_rows"), State("bom-edit-view", "data")],
    running=[
        (Output("button-calculate-bom-price", "disabled"), True, False),
        (Output("button-select-bom", "disabled"), True, False),
    ],
    prevent_initial_call=True,
)
def insert_record_manual_price_and_calculate(nc, sr, edited_bom):
    global rdbms
    df_bom_list = get_bom_list()
    bom_sn = df_bom_list.loc[sr[0]].tolist()[0]
    bom_version = df_bom_list.loc[sr[0]].tolist()[1]
    user_tag = df_bom_list.loc[sr[0]].tolist()[2]
    df_bom_ori = get_original_bom(bom_sn, bom_version, user_tag).to_dict("records")
    ## analyse the changed price records.
    changed = []
    for dori in df_bom_ori:
        for dedit in edited_bom:
            if (str(dori["layer_sn"]) == str(dedit["layer_sn"])) and (
                float(dori["manually_set_price"]) != float(dedit["manually_set_price"])
            ):
                changed.append(dedit)
    # print('changed -> ',changed)
    if len(changed) > 0:
        list_out = []
        for c in changed:
            list_out.append(
                {
                    "part_number": c["part_number"],
                    "part_name": c["part_name"],
                    "manualprice": c["manually_set_price"],
                    "bom_sn": bom_sn,
                    "bom_version": bom_version,
                    "user_tag": user_tag,
                    "record_time": str(datetime.datetime.today())[:19],
                }
            )
        df_out = pd.DataFrame(list_out)
        # print(list_out)
        conn = connect_2_db()
        if rdbms == "postgres":
            df_out.to_sql(
                "manualprice",
                con=conn,
                schema="bom_dev",
                if_exists="append",
                index=False,
            )
        if rdbms == "sqlserver":
            df_out.to_sql("manualprice", con=conn, if_exists="append", index=False)
        conn.dispose()
        ##  #################################################################################   to-do add a spin here.......
        print("new manualdata inserted...")
        calculate_bom(bom_sn, bom_version, user_tag)
        print("calculate complete...")
        df_after_edit = get_original_bom(bom_sn, bom_version, user_tag)
        print("refreshing...")
        return df_after_edit[
            [
                "layer_sn",
                "layer_level",
                "part_number",
                "part_name",
                "qty",
                "total_qty",
                "manually_set_price",
                "latest_po_price",
                "price",
                "updatetime",
            ]
        ].to_dict("records")
    else:
        return edited_bom


## Export BOM to Excel - Download
@callback(
    Output("download-dataframe-xlsx", "data"),
    Input("button-download-bom", "n_clicks"),
    State("bom-table", "selected_rows"),
    State("bom-edit-view", "data"),
    prevent_initial_call=True,
)
def func(n_clicks, sr, bom_edit_data):
    df_bom_list = get_bom_list()
    bom_sn = df_bom_list.loc[sr[0]].tolist()[0]
    bom_version = df_bom_list.loc[sr[0]].tolist()[1]
    user_tag = df_bom_list.loc[sr[0]].tolist()[2]

    file_name = (
        bom_sn
        + "_"
        + bom_version
        + "_"
        + user_tag
        + "_"
        + str(bom_edit_data[0]["updatetime"])[:19]
    )
    sheet_name = bom_sn + "_" + bom_version
    df = pd.DataFrame(bom_edit_data)
    return dcc.send_data_frame(
        df.to_excel, (file_name + ".xlsx"), sheet_name=sheet_name
    )


## providing template download - Download template
@callback(
    Output("download-template", "data"),
    Input("button-download-template", "n_clicks"),
    prevent_initial_call=True,
)
def get_template(n_clicks):
    template_file_content = [
        {
            "bom_sn": "V04test01",
            "bom_version": "test01",
            "user_tag": "王设计",
            "layer_sn": "1",
            "part_number": "PRG01",
            "part_name": "App程序",
            "qty": 1,
            "total_qty": 1,
        },
        {
            "bom_sn": "V04test01",
            "bom_version": "test01",
            "user_tag": "王设计",
            "layer_sn": "1.1",
            "part_number": "CLS01",
            "part_name": "App类",
            "qty": 2,
            "total_qty": 2,
        },
        {
            "bom_sn": "V04test01",
            "bom_version": "test01",
            "user_tag": "王设计",
            "layer_sn": "1.1.1",
            "part_number": "OBJ01",
            "part_name": "App实例",
            "qty": 2,
            "total_qty": 4,
        },
    ]
    df = pd.DataFrame(template_file_content)
    return dcc.send_data_frame(
        df.to_excel, "bom_template.xlsx", sheet_name="templatev0.4"
    )


@app.callback(
    Output("side-bar", "is_open"),
    Output("button-select-bom", "disabled"),
    Input("open-side-bar", "n_clicks"),
    [State("side-bar", "is_open")],
)
def toggle_offcanvas(n1, is_open):
    if "info" in get_bom_list().columns:
        button_switch = True
    else:
        button_switch = False
    if n1:
        return (not is_open, button_switch)
    return (is_open, button_switch)


if __name__ == "__main__":
    app.run(
        debug=debug,
        jupyter_mode=jupyter_mode,
        host=host,
        port=port,
        jupyter_server_url=jupyter_server_url,
    )
    # app.run(host=host, port = port)
