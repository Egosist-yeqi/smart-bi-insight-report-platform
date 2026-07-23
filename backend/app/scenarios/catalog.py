from dataclasses import dataclass
from decimal import Decimal


CSV_HEADERS = (
    "record_id",
    "date",
    "region",
    "province",
    "item_id",
    "item_name",
    "category",
    "customer_type",
    "quantity",
    "amount",
    "profit",
)


@dataclass(frozen=True)
class ScenarioDefinition:
    identifier: str
    title: str
    description: str
    entity_label: str
    amount_label: str
    quantity_label: str
    regions: tuple[tuple[str, str, Decimal], ...]
    items: tuple[tuple[int, str, str, Decimal, Decimal, str], ...]
    question_groups: tuple[tuple[str, tuple[str, ...]], ...]
    field_mappings: tuple[tuple[str, str], ...]


COMMON_QUESTIONS = (
    ("发生了什么", ("本月各区域经营金额排名如何？", "最近30天经营金额趋势如何？")),
    ("为什么发生", ("为什么本月经营金额出现变化？",)),
    ("接下来怎么办", ("本月经营上最需要优先关注哪个区域？",)),
    ("预测与模拟", ("下个月经营金额可能是多少？",)),
)


SCENARIOS = (
    ScenarioDefinition(
        identifier="ecommerce",
        title="电商经营",
        description="围绕商品交易、品类、用户类型和履约区域的经营分析。",
        entity_label="商品",
        amount_label="GMV / 交易额",
        quantity_label="件数",
        regions=(
            ("华东", "上海", Decimal("1.18")),
            ("华南", "广东", Decimal("0.96")),
            ("华北", "北京", Decimal("1.05")),
            ("西南", "四川", Decimal("0.88")),
            ("华中", "湖北", Decimal("0.92")),
        ),
        items=(
            (1, "智能穿戴旗舰款", "数码家电", Decimal("2499"), Decimal("0.23"), "会员用户"),
            (2, "家庭清洁套装", "家居百货", Decimal("399"), Decimal("0.31"), "新客"),
            (3, "运动营养组合", "运动健康", Decimal("599"), Decimal("0.36"), "复购用户"),
            (4, "云端办公年卡", "数字服务", Decimal("799"), Decimal("0.62"), "企业用户"),
            (5, "美妆礼盒", "美妆个护", Decimal("699"), Decimal("0.41"), "会员用户"),
            (6, "厨房精选组合", "食品生鲜", Decimal("299"), Decimal("0.28"), "新客"),
        ),
        question_groups=COMMON_QUESTIONS + (("情景问题", ("如果华东区促销投入增加10%，价格下降5%，GMV会怎样？",)),),
        field_mappings=(("item_name", "商品名称"), ("category", "商品品类"), ("customer_type", "用户类型")),
    ),
    ScenarioDefinition(
        identifier="hospital",
        title="医院运营",
        description="围绕门诊服务、科室、患者类型和院区的运营与收入分析。",
        entity_label="医疗服务",
        amount_label="服务收入",
        quantity_label="服务人次",
        regions=(("东院区", "上海", Decimal("1.12")), ("南院区", "广州", Decimal("0.94")), ("北院区", "北京", Decimal("1.06")), ("西院区", "成都", Decimal("0.89")), ("中心院区", "武汉", Decimal("0.98"))),
        items=((1, "专家门诊", "门诊中心", Decimal("680"), Decimal("0.32"), "医保患者"), (2, "健康体检套餐", "健康管理", Decimal("1280"), Decimal("0.38"), "自费患者"), (3, "影像检查服务", "医学影像", Decimal("880"), Decimal("0.29"), "医保患者"), (4, "日间手术服务", "外科中心", Decimal("5600"), Decimal("0.26"), "住院患者"), (5, "慢病随访服务", "慢病管理", Decimal("360"), Decimal("0.44"), "复诊患者"), (6, "康复治疗服务", "康复中心", Decimal("520"), Decimal("0.35"), "住院患者")),
        question_groups=COMMON_QUESTIONS + (("情景问题", ("如果门诊服务投入增加10%，服务价格调整5%，收入会怎样？",)),),
        field_mappings=(("item_name", "医疗服务"), ("category", "科室/中心"), ("customer_type", "患者类型")),
    ),
    ScenarioDefinition(
        identifier="banking",
        title="银行经营",
        description="围绕网点、金融产品、客群和手续费收入的经营分析。",
        entity_label="金融产品",
        amount_label="业务收入",
        quantity_label="办理笔数",
        regions=(("华东分行", "上海", Decimal("1.16")), ("华南分行", "广州", Decimal("0.95")), ("华北分行", "北京", Decimal("1.07")), ("西南分行", "成都", Decimal("0.90")), ("华中分行", "武汉", Decimal("0.97"))),
        items=((1, "个人消费贷", "零售金融", Decimal("980"), Decimal("0.49"), "个人客户"), (2, "企业结算服务", "交易银行", Decimal("3200"), Decimal("0.52"), "企业客户"), (3, "财富管理组合", "财富管理", Decimal("1880"), Decimal("0.58"), "高净值客户"), (4, "信用卡分期", "信用卡", Decimal("760"), Decimal("0.46"), "个人客户"), (5, "供应链融资", "公司金融", Decimal("4200"), Decimal("0.43"), "企业客户"), (6, "跨境汇兑服务", "国际业务", Decimal("1260"), Decimal("0.51"), "企业客户")),
        question_groups=COMMON_QUESTIONS + (("情景问题", ("如果获客投入增加10%，服务费率调整5%，业务收入会怎样？",)),),
        field_mappings=(("item_name", "金融产品"), ("category", "业务条线"), ("customer_type", "客户分层")),
    ),
    ScenarioDefinition(
        identifier="manufacturing",
        title="制造业经营",
        description="围绕工厂、产品线、客户类型和订单产值的经营分析。",
        entity_label="产品",
        amount_label="订单产值",
        quantity_label="交付数量",
        regions=(("东部工厂", "苏州", Decimal("1.15")), ("南部工厂", "深圳", Decimal("0.93")), ("北部工厂", "天津", Decimal("1.04")), ("西部工厂", "重庆", Decimal("0.87")), ("中部工厂", "武汉", Decimal("0.96"))),
        items=((1, "工业控制柜", "自动化装备", Decimal("8200"), Decimal("0.27"), "直销客户"), (2, "精密传感模组", "核心零部件", Decimal("2600"), Decimal("0.31"), "渠道客户"), (3, "数控工作站", "智能装备", Decimal("16800"), Decimal("0.25"), "直销客户"), (4, "能耗监测终端", "工业物联", Decimal("4300"), Decimal("0.34"), "项目客户"), (5, "设备维保包", "售后服务", Decimal("3600"), Decimal("0.48"), "存量客户"), (6, "质量检测服务", "工业服务", Decimal("5200"), Decimal("0.42"), "项目客户")),
        question_groups=COMMON_QUESTIONS + (("情景问题", ("如果渠道投入增加10%，报价下调5%，订单产值会怎样？",)),),
        field_mappings=(("item_name", "产品/服务"), ("category", "产品线"), ("customer_type", "客户类型")),
    ),
    ScenarioDefinition(
        identifier="internet",
        title="互联网公司经营",
        description="围绕业务线、订阅产品、客户分层和订阅收入的经营分析。",
        entity_label="订阅产品",
        amount_label="订阅收入",
        quantity_label="付费席位",
        regions=(("东区业务组", "上海", Decimal("1.17")), ("南区业务组", "广州", Decimal("0.95")), ("北区业务组", "北京", Decimal("1.08")), ("西区业务组", "成都", Decimal("0.91")), ("中区业务组", "武汉", Decimal("0.98"))),
        items=((1, "协同办公专业版", "SaaS 协同", Decimal("1299"), Decimal("0.67"), "中小企业"), (2, "数据洞察企业版", "数据智能", Decimal("6800"), Decimal("0.71"), "大客户"), (3, "客户运营平台", "营销云", Decimal("3200"), Decimal("0.63"), "中小企业"), (4, "开发者服务包", "开发者平台", Decimal("2600"), Decimal("0.69"), "开发团队"), (5, "安全合规服务", "安全产品", Decimal("4800"), Decimal("0.73"), "大客户"), (6, "智能客服订阅", "AI 应用", Decimal("1800"), Decimal("0.65"), "中小企业")),
        question_groups=COMMON_QUESTIONS + (("情景问题", ("如果市场投入增加10%，订阅价格下调5%，收入会怎样？",)),),
        field_mappings=(("item_name", "订阅产品"), ("category", "业务线"), ("customer_type", "客户分层")),
    ),
)

SCENARIO_BY_ID = {scenario.identifier: scenario for scenario in SCENARIOS}
