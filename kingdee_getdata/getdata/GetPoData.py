import datetime
import json
import os

from k3cloud_webapi_sdk.main import K3CloudApiSdk

#获取采购订单数据
def get_po_data():
    api_sdk = K3CloudApiSdk("http://erp.julan.com.cn:8081/k3cloud/")
    # 获取当前文件所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # conf.ini 在 kingdee_getdata 目录下
    config_path = os.path.abspath(os.path.join(base_dir, "..", "conf.ini"))

    api_sdk.Init(config_path=config_path, config_node="config")

    now = datetime.datetime.now()
    
    # 放宽时间限制：查询过去 90 天到未来 30 天的未关闭订单，确保能抓到历史逾期的
    past_time = now - datetime.timedelta(days=90)
    past_str = past_time.strftime("%Y/%m/%d %H:%M:%S")
    future_time = now + datetime.timedelta(days=30)
    future_str = future_time.strftime("%Y/%m/%d %H:%M:%S")

    # 请求参数
    # 添加了采购订单号 FBILLNO，以便出现问题时能在 ERP 中快速追溯
    para = {
        "FormId": "PUR_PurchaseOrder",
        "FieldKeys": "FBILLNO,F_XJPJ_BASE.FNUMBER,FSUPPLIERID.FNAME,FMATERIALID.FNUMBER,FMATERIALNAME,FQTY,FDELIVERYDATE,FRECEIVEQTY,FREMAINRECEIVEQTY,FSTOCKINQTY,FREMAINSTOCKINQTY",
        "FilterString": [
            # 时间范围：过去90天到未来30天（涵盖已逾期和即将到期的）
            {"Left": "(", "FieldName": "FDELIVERYDATE", "Compare": ">=", "Value": past_str, "Right": ")", "Logic": "0"},
            {"Left": "(", "FieldName": "FDELIVERYDATE", "Compare": "<=", "Value": future_str, "Right": ")", "Logic": "0"},
            # 业务状态：必须是正常未关闭的（A），且单据状态必须是已审核（C）
            {"Left": "(", "FieldName": "FMRPCLOSESTATUS", "Compare": "=", "Value": "A", "Right": ")", "Logic": "0"},
            {"Left": "(", "FieldName": "FDOCUMENTSTATUS", "Compare": "=", "Value": "C", "Right": ")", "Logic": "0"},
            # 核心过滤：只要剩余收料数量大于0（供应商未交齐）或者剩余入库数量大于0（仓库未入完），我们就把它拉出来！
            # 注意：这里的 Logic 是 OR (1)，所以我们需要用括号把这两个 OR 包起来，和前面的条件形成 AND 关系。
            {"Left": "((", "FieldName": "FREMAINRECEIVEQTY", "Compare": ">", "Value": "0", "Right": "", "Logic": "1"},
            {"Left": "", "FieldName": "FREMAINSTOCKINQTY", "Compare": ">", "Value": "0", "Right": "))", "Logic": "0"}
        ],
        "OrderString": "FDELIVERYDATE ASC", # 按交货日期正序（越早交货的排在越前面，越急迫）
        "TopRowCount": 0,
        "StartRow": 0,
        "Limit": 2000,
        "SubSystemId": ""
    }
    # 调用接口
    response = api_sdk.ExecuteBillQuery(para)
    #print("po接口返回结果：" + response)
    res = json.loads(response)
    return res

#get_po_data()








