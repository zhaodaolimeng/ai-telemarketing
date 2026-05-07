#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户画像和业务状态数据模型 - T5.1 & T5.2
支持话术模板化配置
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime, date


class CustomerPersonaType(Enum):
    """客户类型"""
    COOPERATIVE = "cooperative"
    BUSY = "busy"
    NEGOTIATING = "negotiating"
    RESISTANT = "resistant"
    SILENT = "silent"
    FORGETFUL = "forgetful"
    EXCUSE_MASTER = "excuse_master"


class CollectionStage(Enum):
    """催收阶段"""
    H2 = "H2"  # 早期
    H1 = "H1"  # 中期
    S0 = "S0"  # 晚期


class IncomeLevel(Enum):
    """收入水平"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EmploymentStatus(Enum):
    """就业状态"""
    EMPLOYED = "employed"
    SELF_EMPLOYED = "self_employed"
    UNEMPLOYED = "unemployed"
    RETIRED = "retired"


class HouseOwnership(Enum):
    """住房情况"""
    OWNED = "owned"
    RENTED = "rented"
    FAMILY = "family"


@dataclass
class UserProfile:
    """用户画像"""
    # 基本信息
    name: str = "Pak/Bu"
    gender: Optional[str] = None
    age: Optional[int] = None
    marital_status: Optional[str] = None
    education_level: Optional[str] = None

    # 联系方式
    phone: Optional[str] = None
    address: Optional[str] = None

    # 职业/收入
    occupation: Optional[str] = None
    income_level: IncomeLevel = IncomeLevel.MEDIUM
    employment_status: EmploymentStatus = EmploymentStatus.EMPLOYED

    # 家庭信息
    family_size: Optional[int] = None
    dependents: Optional[int] = None
    house_ownership: HouseOwnership = HouseOwnership.OWNED


@dataclass
class BusinessContext:
    """业务状态"""
    # 产品信息
    product_name: str = "Extra Cash"
    loan_amount: Optional[float] = None
    tenure: Optional[int] = None
    interest_rate: Optional[float] = None

    # 还款状态
    current_stage: CollectionStage = CollectionStage.H2
    days_overdue: int = 0
    amount_overdue: Optional[float] = None
    total_outstanding: Optional[float] = None
    missed_payments: int = 0

    # 历史记录
    history_repayment_rate: Optional[float] = None
    number_of_loans: int = 0
    last_payment_date: Optional[date] = None
    last_contact_date: Optional[date] = None

    # 催收状态
    times_contacted_this_cycle: int = 0
    last_contact_result: Optional[str] = None
    previously_agreed_time: Optional[str] = None


@dataclass
class TemplateVariable:
    """模板变量"""
    name: str
    value: Any
    default: Optional[Any] = None


class ScriptTemplateEngine:
    """话术模板引擎 - T5.3"""

    def __init__(self, user_profile: UserProfile, business_context: BusinessContext):
        self.profile = user_profile
        self.context = business_context
        self._variable_cache: Dict[str, Any] = {}

    def _build_variable_map(self) -> Dict[str, Any]:
        """构建变量映射表"""
        if self._variable_cache:
            return self._variable_cache

        variables = {
            # 通用变量
            "name": self.profile.name,
            "stage": self.context.current_stage.value,
            "days_overdue": str(self.context.days_overdue),
            "amount_overdue": str(self.context.amount_overdue) if self.context.amount_overdue else "",
            "total_outstanding": str(self.context.total_outstanding) if self.context.total_outstanding else "",
            "loan_amount": str(self.context.loan_amount) if self.context.loan_amount else "",
            "product_name": self.context.product_name,

            # 用户信息变量
            "gender": self.profile.gender or "",
            "age": str(self.profile.age) if self.profile.age else "",
            "occupation": self.profile.occupation or "",
            "income_level": self.profile.income_level.value,
            "family_size": str(self.profile.family_size) if self.profile.family_size else "",
            "dependents": str(self.profile.dependents) if self.profile.dependents else "",

            # 历史记录变量
            "history_repayment_rate": f"{self.context.history_repayment_rate:.0%}" if self.context.history_repayment_rate else "",
            "number_of_loans": str(self.context.number_of_loans),
            "times_contacted": str(self.context.times_contacted_this_cycle),
            "last_contact_result": self.context.last_contact_result or "",
            "previously_agreed_time": self.context.previously_agreed_time or "",
        }

        self._variable_cache = variables
        return variables

    def render(self, template: str, **kwargs) -> str:
        """渲染模板
        支持 {variable_name} 格式变量
        支持默认值: {variable_name|default_value}
        """
        variables = self._build_variable_map()
        variables.update(kwargs)

        result = template
        import re

        # 匹配 {name|default} 格式
        def replace_var(match):
            var_parts = match.group(1).split("|", 1)
            var_name = var_parts[0].strip()
            default = var_parts[1].strip() if len(var_parts) > 1 else ""

            value = variables.get(var_name, default)
            return str(value) if value is not None else default

        # 替换所有变量
        result = re.sub(r'\{([^}]+)\}', replace_var, result)
        return result


class ScriptSelector:
    """话术选择策略 - T5.4 & T5.5"""

    def __init__(self, user_profile: UserProfile, business_context: BusinessContext):
        self.profile = user_profile
        self.context = business_context

    def select_by_stage(self, stage_scripts: Dict[str, List[str]]) -> List[str]:
        """T5.4 - 根据催收阶段选择话术"""
        stage = self.context.current_stage.value
        return stage_scripts.get(stage, stage_scripts.get("default", []))

    def select_by_persona(self, persona_scripts: Dict[str, List[str]]) -> List[str]:
        """根据用户特征选择话术"""
        # 基于收入水平的选择
        income = self.profile.income_level.value
        if income in persona_scripts:
            return persona_scripts[income]

        # 基于职业的选择
        if self.profile.occupation:
            occ = self.profile.occupation.lower()
            for key in persona_scripts:
                if key in occ:
                    return persona_scripts[key]

        return persona_scripts.get("default", [])

    def select_by_history(self, history_scripts: Dict[str, List[str]]) -> List[str]:
        """T5.5 - 根据历史记录选择话术"""
        # 首次联系
        if self.context.times_contacted_this_cycle == 0:
            return history_scripts.get("first_contact", history_scripts.get("default", []))

        # 有失信记录
        if self.context.last_contact_result == "promised_but_default":
            return history_scripts.get("broken_promise", history_scripts.get("default", []))

        # 历史还款记录良好
        if self.context.history_repayment_rate and self.context.history_repayment_rate >= 0.9:
            return history_scripts.get("good_history", history_scripts.get("default", []))

        return history_scripts.get("default", [])


@dataclass
class ScriptConfig:
    """话术配置 - T5.6 模板配置管理"""
    name: str
    description: str
    templates: Dict[str, List[str]]
    selection_rules: Dict[str, Dict[str, List[str]]]

    @classmethod
    def create_default(cls) -> 'ScriptConfig':
        """创建默认配置"""
        return cls(
            name="default_collection",
            description="默认催收话术配置",
            templates={
                "H2_greeting": ["Halo {name}, selamat siang.", "Halo {name}!"],
                "H2_purpose": ["Untuk pinjaman ya {name}.", "Saya mau mengingatkan tentang pinjaman Anda."],
                "H2_ask_time": ["Kapan kira-kira Anda bisa bayar?", "Jam berapa ya?"],
                "H1_greeting": ["Halo {name}, selamat pagi.", "Halo {name}!"],
                "H1_purpose": ["Untuk pinjaman yang sudah jatuh tempo {name}."],
                "S0_greeting": ["Halo {name}, selamat sore."],
                "S0_purpose": ["Kita bicara tentang pinjaman yang sudah agak lama ya {name}."],
            },
            selection_rules={
                "by_stage": {
                    "H2": ["H2_greeting", "H2_purpose", "H2_ask_time"],
                    "H1": ["H1_greeting", "H1_purpose"],
                    "S0": ["S0_greeting", "S0_purpose"],
                }
            }
        )


# 使用示例
if __name__ == "__main__":
    print("=" * 70)
    print("用户画像与话术模板示例")
    print("=" * 70)

    # 创建用户画像
    profile = UserProfile(
        name="Pak Budi",
        occupation="employee",
        income_level=IncomeLevel.MEDIUM,
    )

    # 创建业务状态
    context = BusinessContext(
        product_name="Extra Cash",
        current_stage=CollectionStage.H2,
        days_overdue=7,
        amount_overdue=500000,
        times_contacted_this_cycle=0,
    )

    # 模板引擎
    engine = ScriptTemplateEngine(profile, context)

    # 渲染示例
    print("\n📝 模板渲染示例:")
    templates = [
        "Halo {name}, selamat siang.",
        "Untuk pinjaman yang sudah terlambat {days_overdue} hari.",
        "Kapan bisa bayar {name}?",
        "Halo {name}! Sudah lama tidak mendengar kabar Anda. Apakah Anda ingat janji jam {previously_agreed_time|nanti}?",
    ]

    for t in templates:
        result = engine.render(t)
        print(f"  模板: {t}")
        print(f"  结果: {result}\n")

    # 话术选择器
    selector = ScriptSelector(profile, context)

    print("\n🎯 话术选择策略:")
    stage_scripts = {
        "H2": ["温和提醒", "礼貌询问"],
        "H1": ["严肃提醒", "了解情况"],
        "S0": ["施压", "协商"],
        "default": ["通用话术"],
    }
    selected = selector.select_by_stage(stage_scripts)
    print(f"  阶段 {context.current_stage.value}: {selected}")

    # 配置示例
    config = ScriptConfig.create_default()
    print(f"\n📋 默认配置: {config.name}")
    print(f"  模板数: {len(config.templates)}")

    print("\n" + "=" * 70)
    print("✅ 用户画像与话术模板系统就绪！")
    print("=" * 70)
