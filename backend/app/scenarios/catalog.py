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
class ScenarioQuestion:
    text: str
    intent: dict[str, object]
    decision_kind: str | None = None


@dataclass(frozen=True)
class ScenarioDefinition:
    identifier: str
    title: str
    description: str
    entity_label: str
    amount_label: str
    quantity_label: str
    region_label: str
    category_label: str
    customer_label: str
    root_cause_checks: tuple[str, ...]
    recommendation_actions: tuple[str, ...]
    regions: tuple[tuple[str, str, Decimal], ...]
    items: tuple[tuple[int, str, str, Decimal, Decimal, str], ...]
    question_groups: tuple[tuple[str, tuple[ScenarioQuestion, ...]], ...]
    field_mappings: tuple[tuple[str, str], ...]


def _intent(
    metric: str = "amount",
    dimensions: tuple[str, ...] = (),
    *,
    time_range: str = "latest_month",
    sort_direction: str = "desc",
    analysis_kind: str = "ranking",
    filters: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "metric": metric,
        "dimensions": list(dimensions),
        "time_range": time_range,
        "sort_direction": sort_direction,
        "analysis_kind": analysis_kind,
        "filters": filters or {},
    }


def _scenario_questions(
    *,
    amount_label: str,
    quantity_label: str,
    entity_label: str,
    region_label: str,
    category_label: str,
    customer_label: str,
    focus_region: str,
    investment_label: str,
) -> tuple[tuple[str, tuple[ScenarioQuestion, ...]], ...]:
    return (
        (
            "发生了什么",
            (
                ScenarioQuestion(f"本月各{region_label}{amount_label}排名如何？", _intent(dimensions=("region",))),
                ScenarioQuestion(f"最近30天{amount_label}趋势如何？", _intent(dimensions=("week",), time_range="last_30_days", sort_direction="asc", analysis_kind="trend")),
                ScenarioQuestion(f"本月各{category_label}{amount_label}排名如何？", _intent(dimensions=("category",))),
                ScenarioQuestion(f"本月各{customer_label}{amount_label}贡献如何？", _intent(dimensions=("customer_type",))),
                ScenarioQuestion(f"本月{entity_label}{amount_label}排名如何？", _intent(dimensions=("product_name",))),
                ScenarioQuestion(f"本月各{region_label}{quantity_label}排名如何？", _intent(metric="quantity", dimensions=("region",))),
                ScenarioQuestion(f"本月各{category_label}毛利排名如何？", _intent(metric="profit", dimensions=("category",))),
            ),
        ),
        (
            "为什么发生",
            (
                ScenarioQuestion(f"为什么本月{amount_label}出现变化？", _intent(dimensions=("month",), time_range="all", sort_direction="asc", analysis_kind="comparison"), "root_cause"),
                ScenarioQuestion(f"为什么{focus_region}{amount_label}出现变化？", _intent(dimensions=("month",), time_range="all", sort_direction="asc", analysis_kind="comparison", filters={"region": focus_region}), "root_cause"),
                ScenarioQuestion(f"哪个{category_label}的毛利偏低，需要核查？", _intent(metric="profit", dimensions=("category",), sort_direction="asc")),
                ScenarioQuestion(f"哪个{customer_label}的{amount_label}偏低，需要核查？", _intent(dimensions=("customer_type",), sort_direction="asc")),
            ),
        ),
        (
            "接下来怎么办",
            (
                ScenarioQuestion(f"本月{amount_label}最需要优先关注哪个{region_label}？", _intent(dimensions=("region",), sort_direction="asc", analysis_kind="detail"), "recommendation"),
                ScenarioQuestion(f"针对{focus_region}{amount_label}表现，下一步优先核查什么？", _intent(dimensions=("region",), sort_direction="asc", analysis_kind="detail", filters={"region": focus_region}), "recommendation"),
                ScenarioQuestion(f"本月各{region_label}表现存在差异，应先采取什么行动？", _intent(dimensions=("region",), sort_direction="asc", analysis_kind="detail"), "recommendation"),
            ),
        ),
        (
            "预测与模拟",
            (
                ScenarioQuestion(f"下个月{amount_label}可能是多少？", _intent(dimensions=("month",), time_range="all", sort_direction="asc", analysis_kind="trend"), "forecast"),
                ScenarioQuestion(f"未来一个月{amount_label}可能如何变化？", _intent(dimensions=("month",), time_range="all", sort_direction="asc", analysis_kind="trend"), "forecast"),
                ScenarioQuestion(f"如果{focus_region}{investment_label}投入增加10%，价格下调5%，{amount_label}会怎样？", _intent(dimensions=("region",), time_range="latest_month", analysis_kind="detail", filters={"region": focus_region}), "promotion_scenario"),
            ),
        ),
    )


SCENARIOS = (
    ScenarioDefinition(
        identifier="ecommerce",
        title="电商经营",
        description="围绕商品交易、品类、用户类型和履约区域的经营分析。",
        entity_label="商品",
        amount_label="GMV / 交易额",
        quantity_label="件数",
        region_label="区域",
        category_label="商品品类",
        customer_label="用户类型",
        root_cause_checks=("商品组合与折扣变化", "重点用户订单与复购", "库存、履约和区域投放节奏"),
        recommendation_actions=("先核查{region}的商品组合、重点用户订单与履约节奏，确认问题集中环节。", "对确认下滑的商品或用户建立 7 天跟进清单，并观察转化和复购变化。", "促销或降价先小范围验证，同时设置毛利底线，再决定是否扩大投入。"),
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
        question_groups=_scenario_questions(
            amount_label="GMV / 交易额", quantity_label="件数", entity_label="商品",
            region_label="区域", category_label="商品品类", customer_label="用户类型",
            focus_region="华东", investment_label="促销",
        ),
        field_mappings=(("region", "区域"), ("item_name", "商品名称"), ("category", "商品品类"), ("customer_type", "用户类型")),
    ),
    ScenarioDefinition(
        identifier="hospital",
        title="医院运营",
        description="围绕门诊服务、科室、患者类型和院区的运营与收入分析。",
        entity_label="医疗服务",
        amount_label="服务收入",
        quantity_label="服务人次",
        region_label="院区",
        category_label="科室/中心",
        customer_label="患者类型",
        root_cause_checks=("科室服务结构与收费项目", "重点患者类型的复诊与检查服务", "排班、号源、设备与院区服务能力"),
        recommendation_actions=("先核查{region}的科室服务结构、号源与检查排期，定位影响服务收入的环节。", "对收入下降的服务项目建立 7 天复盘清单，跟踪服务人次与复诊变化。", "新增服务投入先在重点科室试点，并同时评估服务质量与资源承载能力。"),
        regions=(("东院区", "上海", Decimal("1.12")), ("南院区", "广州", Decimal("0.94")), ("北院区", "北京", Decimal("1.06")), ("西院区", "成都", Decimal("0.89")), ("中心院区", "武汉", Decimal("0.98"))),
        items=((1, "专家门诊", "门诊中心", Decimal("680"), Decimal("0.32"), "医保患者"), (2, "健康体检套餐", "健康管理", Decimal("1280"), Decimal("0.38"), "自费患者"), (3, "影像检查服务", "医学影像", Decimal("880"), Decimal("0.29"), "医保患者"), (4, "日间手术服务", "外科中心", Decimal("5600"), Decimal("0.26"), "住院患者"), (5, "慢病随访服务", "慢病管理", Decimal("360"), Decimal("0.44"), "复诊患者"), (6, "康复治疗服务", "康复中心", Decimal("520"), Decimal("0.35"), "住院患者")),
        question_groups=_scenario_questions(
            amount_label="服务收入", quantity_label="服务人次", entity_label="医疗服务",
            region_label="院区", category_label="科室/中心", customer_label="患者类型",
            focus_region="东院区", investment_label="门诊服务",
        ),
        field_mappings=(("region", "院区"), ("item_name", "医疗服务"), ("category", "科室/中心"), ("customer_type", "患者类型")),
    ),
    ScenarioDefinition(
        identifier="banking",
        title="银行经营",
        description="围绕网点、金融产品、客群和手续费收入的经营分析。",
        entity_label="金融产品",
        amount_label="业务收入",
        quantity_label="办理笔数",
        region_label="分行",
        category_label="业务条线",
        customer_label="客户分层",
        root_cause_checks=("产品费率与业务结构", "重点客户的交易与资产配置", "网点触达、审批与客户经理跟进节奏"),
        recommendation_actions=("先核查{region}的产品费率、重点客户交易与客户经理跟进，确认收入变化环节。", "对下滑业务条线建立 7 天客户清单，跟踪办理笔数和转化变化。", "获客或费率调整先在目标客群小范围验证，并同步监控合规与收益边界。"),
        regions=(("华东分行", "上海", Decimal("1.16")), ("华南分行", "广州", Decimal("0.95")), ("华北分行", "北京", Decimal("1.07")), ("西南分行", "成都", Decimal("0.90")), ("华中分行", "武汉", Decimal("0.97"))),
        items=((1, "个人消费贷", "零售金融", Decimal("980"), Decimal("0.49"), "个人客户"), (2, "企业结算服务", "交易银行", Decimal("3200"), Decimal("0.52"), "企业客户"), (3, "财富管理组合", "财富管理", Decimal("1880"), Decimal("0.58"), "高净值客户"), (4, "信用卡分期", "信用卡", Decimal("760"), Decimal("0.46"), "个人客户"), (5, "供应链融资", "公司金融", Decimal("4200"), Decimal("0.43"), "企业客户"), (6, "跨境汇兑服务", "国际业务", Decimal("1260"), Decimal("0.51"), "企业客户")),
        question_groups=_scenario_questions(
            amount_label="业务收入", quantity_label="办理笔数", entity_label="金融产品",
            region_label="分行", category_label="业务条线", customer_label="客户分层",
            focus_region="华东分行", investment_label="获客",
        ),
        field_mappings=(("region", "分行"), ("item_name", "金融产品"), ("category", "业务条线"), ("customer_type", "客户分层")),
    ),
    ScenarioDefinition(
        identifier="manufacturing",
        title="制造业经营",
        description="围绕工厂、产品线、客户类型和订单产值的经营分析。",
        entity_label="产品",
        amount_label="订单产值",
        quantity_label="交付数量",
        region_label="工厂",
        category_label="产品线",
        customer_label="客户类型",
        root_cause_checks=("产品线结构与报价变化", "重点客户订单、交付与验收节点", "产能、物料、质量与渠道执行节奏"),
        recommendation_actions=("先核查{region}的订单结构、报价、交付与验收节点，确认产值变化环节。", "对下滑产品线建立 7 天项目清单，跟踪订单、交付和回款变化。", "渠道或报价调整先在目标产品线试点，并设置毛利与产能边界。"),
        regions=(("东部工厂", "苏州", Decimal("1.15")), ("南部工厂", "深圳", Decimal("0.93")), ("北部工厂", "天津", Decimal("1.04")), ("西部工厂", "重庆", Decimal("0.87")), ("中部工厂", "武汉", Decimal("0.96"))),
        items=((1, "工业控制柜", "自动化装备", Decimal("8200"), Decimal("0.27"), "直销客户"), (2, "精密传感模组", "核心零部件", Decimal("2600"), Decimal("0.31"), "渠道客户"), (3, "数控工作站", "智能装备", Decimal("16800"), Decimal("0.25"), "直销客户"), (4, "能耗监测终端", "工业物联", Decimal("4300"), Decimal("0.34"), "项目客户"), (5, "设备维保包", "售后服务", Decimal("3600"), Decimal("0.48"), "存量客户"), (6, "质量检测服务", "工业服务", Decimal("5200"), Decimal("0.42"), "项目客户")),
        question_groups=_scenario_questions(
            amount_label="订单产值", quantity_label="交付数量", entity_label="产品",
            region_label="工厂", category_label="产品线", customer_label="客户类型",
            focus_region="东部工厂", investment_label="渠道",
        ),
        field_mappings=(("region", "工厂"), ("item_name", "产品/服务"), ("category", "产品线"), ("customer_type", "客户类型")),
    ),
    ScenarioDefinition(
        identifier="internet",
        title="互联网公司经营",
        description="围绕业务线、订阅产品、客户分层和订阅收入的经营分析。",
        entity_label="订阅产品",
        amount_label="订阅收入",
        quantity_label="付费席位",
        region_label="业务组",
        category_label="业务线",
        customer_label="客户分层",
        root_cause_checks=("订阅产品结构与定价变化", "重点客户续费、扩容与流失情况", "获客、转化、交付与客户成功跟进节奏"),
        recommendation_actions=("先核查{region}的订阅结构、续费客户与获客转化，确认收入变化环节。", "对下滑业务线建立 7 天客户成功清单，跟踪续费、扩容和流失变化。", "市场投入或订阅价格调整先在目标客群试点，并设置续费率与毛利边界。"),
        regions=(("东区业务组", "上海", Decimal("1.17")), ("南区业务组", "广州", Decimal("0.95")), ("北区业务组", "北京", Decimal("1.08")), ("西区业务组", "成都", Decimal("0.91")), ("中区业务组", "武汉", Decimal("0.98"))),
        items=((1, "协同办公专业版", "SaaS 协同", Decimal("1299"), Decimal("0.67"), "中小企业"), (2, "数据洞察企业版", "数据智能", Decimal("6800"), Decimal("0.71"), "大客户"), (3, "客户运营平台", "营销云", Decimal("3200"), Decimal("0.63"), "中小企业"), (4, "开发者服务包", "开发者平台", Decimal("2600"), Decimal("0.69"), "开发团队"), (5, "安全合规服务", "安全产品", Decimal("4800"), Decimal("0.73"), "大客户"), (6, "智能客服订阅", "AI 应用", Decimal("1800"), Decimal("0.65"), "中小企业")),
        question_groups=_scenario_questions(
            amount_label="订阅收入", quantity_label="付费席位", entity_label="订阅产品",
            region_label="业务组", category_label="业务线", customer_label="客户分层",
            focus_region="东区业务组", investment_label="市场",
        ),
        field_mappings=(("region", "业务组"), ("item_name", "订阅产品"), ("category", "业务线"), ("customer_type", "客户分层")),
    ),
)

SCENARIO_BY_ID = {scenario.identifier: scenario for scenario in SCENARIOS}
TEMPLATE_BY_QUESTION = {
    question.text: question
    for scenario in SCENARIOS
    for _group_title, questions in scenario.question_groups
    for question in questions
}
TEMPLATE_SCENARIO_BY_QUESTION = {
    question.text: scenario
    for scenario in SCENARIOS
    for _group_title, questions in scenario.question_groups
    for question in questions
}


def template_for_question(question: str) -> ScenarioQuestion | None:
    return TEMPLATE_BY_QUESTION.get(question.strip())


def scenario_for_template_question(question: str) -> ScenarioDefinition | None:
    return TEMPLATE_SCENARIO_BY_QUESTION.get(question.strip())
