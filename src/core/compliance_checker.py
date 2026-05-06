#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合规检查器
用于检测催收话术是否符合监管要求，避免违规内容
"""
import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import json


class ComplianceRule:
    """合规规则"""

    def __init__(
        self,
        rule_id: str,
        description: str,
        severity: str,  # high/medium/low
        check_type: str,  # keyword/regex/semantic
        patterns: List[str],
        suggestion: str
    ):
        self.rule_id = rule_id
        self.description = description
        self.severity = severity
        self.check_type = check_type
        self.patterns = [re.compile(p, re.IGNORECASE) if check_type == "regex" else p.lower() for p in patterns]
        self.suggestion = suggestion


class ComplianceChecker:
    """合规检查器"""

    def __init__(self, rules_file: Optional[str] = None):
        self.rules: List[ComplianceRule] = []
        self._load_rules(rules_file)

    def _load_rules(self, rules_file: Optional[str] = None):
        """加载规则库"""
        if rules_file is None:
            # 使用内置规则
            self._load_builtin_rules()
        else:
            # 从文件加载规则
            with open(rules_file, "r", encoding="utf-8") as f:
                rules_data = json.load(f)
            for rule_data in rules_data:
                rule = ComplianceRule(**rule_data)
                self.rules.append(rule)

    def _load_builtin_rules(self):
        """加载内置合规规则"""
        builtin_rules = [
            # 高风险违规规则
            {
                "rule_id": "C-001",
                "description": "禁止使用辱骂性词汇",
                "severity": "high",
                "check_type": "keyword",
                "patterns": ["anjing", "babi", "bodoh", "gila", "kurang ajar", "sombong", "brengsek", "tai", "bangke", "jancuk", "asu"],
                "suggestion": "禁止使用任何辱骂、侮辱用户的词汇，保持专业沟通"
            },
            {
                "rule_id": "C-002",
                "description": "禁止威胁用户",
                "severity": "high",
                "check_type": "keyword",
                "patterns": [
                    "saya akan datang ke rumah kamu", "kami akan datang ke rumah kamu",
                    "kami akan datangi rumah kamu", "saya akan datangi rumah kamu",
                    "saya akan telepon keluarga kamu", "kami akan telepon keluarga kamu",
                    "saya akan hubungi keluarga kamu", "kami akan hubungi keluarga kamu",
                    "kamu akan masuk penjara", "kamu akan ditahan", "polisi akan tangkap kamu",
                    "kami akan laporkan ke polisi", "saya akan laporkan ke polisi",
                    "ancam", "jika tidak bayar kamu akan",
                    "kami akan datangi tempat kerja kamu", "saya akan datangi tempat kerja kamu",
                    "saya akan paksa kamu bayar", "kami akan paksa kamu bayar",
                    "kami akan gunakan cara kekerasan", "saya akan gunakan cara kekerasan",
                    "kamu akan menyesal", "jangan buat saya marah", "jangan buat kami marah",
                    "kami akan bawa ke jalur hukum", "saya akan bawa ke jalur hukum"
                ],
                "suggestion": "禁止使用任何威胁性语言，包括威胁上门、联系家人、报警、使用暴力等"
            },
            {
                "rule_id": "C-003",
                "description": "禁止泄露/散播用户隐私",
                "severity": "high",
                "check_type": "keyword",
                "patterns": [
                    "saya akan sebar data kamu", "kami akan umumkan data kamu",
                    "semua orang akan tahu kamu hutang", "kamu malu jika teman kamu tahu",
                    "kami akan sebar informasi pribadi kamu", "kami akan kirim surat ke RT/RW",
                    "kami akan kasih tau tetangga kamu", "kami akan umumkan ke sosial media",
                    "data kamu akan kami masukkan daftar hitam", "nama kamu akan kami sebar ke seluruh kota",
                    "sebar data", "umumkan data", "kasih tau keluarga", "kasih tau tetangga"
                ],
                "suggestion": "禁止泄露用户的负债信息，禁止以公开隐私、联系家人邻居等方式威胁用户"
            },
            {
                "rule_id": "C-004",
                "description": "禁止虚假承诺",
                "severity": "high",
                "check_type": "keyword",
                "patterns": [
                    "jika bayar sekarang bunga dihapus", "bisa hapus catatan buruk di BI",
                    "kami bisa hapus data kamu di SLIK", "bayar sekarang tidak ada denda"
                ],
                "suggestion": "禁止做出不符合公司政策的虚假承诺，包括减免利息、删除征信记录等"
            },
            {
                "rule_id": "C-005",
                "description": "禁止冒充其他机构人员",
                "severity": "high",
                "check_type": "keyword",
                "patterns": [
                    "saya dari polisi", "saya dari kejaksaan", "saya dari pengadilan",
                    "saya dari Bank Indonesia", "saya dari OJK", "saya dari pemerintah",
                    "kami bekerja sama dengan polisi", "kami bekerja sama dengan OJK",
                    "kami adalah petugas penagihan pemerintah"
                ],
                "suggestion": "禁止冒充公检法、监管机构、政府工作人员，必须如实告知身份为催收人员"
            },
            {
                "rule_id": "C-006",
                "description": "禁止骚扰第三方联系人",
                "severity": "high",
                "check_type": "keyword",
                "patterns": [
                    "kami akan hubungi teman kamu", "kami akan telepon kantor kamu",
                    "kami akan hubungi keluarga besar kamu", "kami akan telepon semua kontak kamu",
                    "kami akan kirim surat ke tempat kerja kamu", "kami akan datangi kantor kamu"
                ],
                "suggestion": "禁止联系除用户本人及授权担保人之外的第三方人员，禁止骚扰用户的工作单位"
            },

            # 中风险违规规则
            {
                "rule_id": "C-011",
                "description": "禁止使用诱导性表述",
                "severity": "medium",
                "check_type": "keyword",
                "patterns": [
                    "bayar sekarang dapat hadiah", "bayar hari ini dapat diskon",
                    "jika bayar hari ini ada bonus"
                ],
                "suggestion": "禁止使用礼品、折扣等方式诱导用户还款，除非是公司官方活动"
            },
            {
                "rule_id": "C-012",
                "description": "禁止在不合适时间催收",
                "severity": "medium",
                "check_type": "keyword",
                "patterns": [
                    "kenapa tidak jawab telepon malam hari", "saya telepon kamu jam 10 malam"
                ],
                "suggestion": "禁止在晚上9点到早上8点之间催收，避免打扰用户休息"
            },
            {
                "rule_id": "C-013",
                "description": "禁止重复拨打骚扰",
                "severity": "medium",
                "check_type": "keyword",
                "patterns": [
                    "saya akan telepon kamu lagi nanti", "kami akan hubungi kamu terus",
                    "kami telepon kamu setiap hari sampai bayar"
                ],
                "suggestion": "禁止一天拨打超过3次，禁止连续骚扰用户"
            },
            {
                "rule_id": "C-014",
                "description": "禁止询问无关信息",
                "severity": "medium",
                "check_type": "keyword",
                "patterns": [
                    "kamu kerja dimana", "gaji kamu berapa", "istri kamu kerja apa",
                    "anak kamu sekolah dimana"
                ],
                "suggestion": "只询问和还款相关的信息，禁止询问用户的隐私信息"
            },
            {
                "rule_id": "C-015",
                "description": "禁止使用不文明、粗鲁用语",
                "severity": "medium",
                "check_type": "regex",
                "patterns": [
                    r"\bloh\b", r"\bah\b", r"\bdong\b", r"\bdeh\b", r"\bnih\b", r"\bmah\b", r"\blah\b",
                    r"\bdong ah\b", r"\bngapain sih\b", r"\bkenapa sih\b",
                    r"\bgak usah banyak bicara\b", r"\bcepat bayar\b", r"\bjangan lambat\b",
                    r"\bkamu bikin repot\b", r"\bsaya sudah capek hubungi kamu\b",
                    r"\bjangan pura-pura tidak tahu\b"
                ],
                "suggestion": "使用正式、专业、礼貌的沟通用语，避免使用口语化、粗鲁、不耐烦的表述"
            },

            # 低风险提示规则
            {
                "rule_id": "C-021",
                "description": "建议使用礼貌用语",
                "severity": "low",
                "check_type": "keyword",
                "patterns": [],  # 反向检查，应该包含礼貌用语
                "suggestion": "建议使用礼貌用语，如'terima kasih', 'maaf', 'permisi'等"
            },
            {
                "rule_id": "C-022",
                "description": "建议使用用户称呼",
                "severity": "low",
                "check_type": "keyword",
                "patterns": [],  # 反向检查，应该包含用户称呼
                "suggestion": "建议使用用户尊称，如'Pak', 'Bu'等，提高用户体验"
            },
            {
                "rule_id": "C-023",
                "description": "建议表达理解",
                "severity": "low",
                "check_type": "keyword",
                "patterns": [],  # 反向检查，应该包含理解用户的表述
                "suggestion": "面对用户的困难，建议先表示理解，如'saya mengerti', 'paham'等"
            }
        ]

        for rule_data in builtin_rules:
            rule = ComplianceRule(**rule_data)
            self.rules.append(rule)

    def check(self, text: str) -> Tuple[bool, List[Dict]]:
        """
        检查文本是否合规
        返回: (是否合规, 违规详情列表)
        """
        if not text:
            return True, []

        text_lower = text.lower()
        violations = []

        for rule in self.rules:
            if rule.check_type == "keyword":
                for pattern in rule.patterns:
                    if isinstance(pattern, str) and pattern in text_lower:
                        violations.append({
                            "rule_id": rule.rule_id,
                            "description": rule.description,
                            "severity": rule.severity,
                            "matched_text": pattern,
                            "suggestion": rule.suggestion
                        })
            elif rule.check_type == "regex":
                for pattern in rule.patterns:
                    match = pattern.search(text_lower)
                    if match:
                        violations.append({
                            "rule_id": rule.rule_id,
                            "description": rule.description,
                            "severity": rule.severity,
                            "matched_text": match.group(),
                            "suggestion": rule.suggestion
                        })

        # 反向检查（应该包含的内容）
        # C-021: 礼貌用语检查
        polite_words = ["terima kasih", "maaf", "permisi", "selamat pagi", "selamat siang", "selamat sore"]
        has_polite = any(word in text_lower for word in polite_words)
        if not has_polite and len(text.split()) > 3:
            c021 = next(r for r in self.rules if r.rule_id == "C-021")
            violations.append({
                "rule_id": c021.rule_id,
                "description": c021.description,
                "severity": c021.severity,
                "matched_text": "",
                "suggestion": c021.suggestion
            })

        # C-022: 用户称呼检查
        honorific_words = ["pak", "bu", "bapak", "ibu"]
        has_honorific = any(word in text_lower for word in honorific_words)
        if not has_honorific and len(text.split()) > 4:
            c022 = next(r for r in self.rules if r.rule_id == "C-022")
            violations.append({
                "rule_id": c022.rule_id,
                "description": c022.description,
                "severity": c022.severity,
                "matched_text": "",
                "suggestion": c022.suggestion
            })

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        violations.sort(key=lambda x: severity_order[x["severity"]])

        # 只要有high级别的违规，就判定为不合规
        is_compliant = all(v["severity"] != "high" for v in violations)

        return is_compliant, violations

    def check_conversation(self, conversation: List[Dict]) -> Tuple[bool, List[Dict]]:
        """
        检查整个对话的合规性
        conversation: 对话列表，每个元素包含'agent'和'customer'字段
        """
        all_violations = []
        overall_compliant = True

        for i, turn in enumerate(conversation):
            agent_text = turn.get("agent", "")
            if agent_text:
                is_ok, violations = self.check(agent_text)
                if not is_ok:
                    overall_compliant = False
                for v in violations:
                    v["turn"] = i + 1
                    v["text"] = agent_text
                    all_violations.append(v)

        return overall_compliant, all_violations

    def generate_report(self, violations: List[Dict]) -> str:
        """生成合规检查报告"""
        if not violations:
            return "✅ 合规检查通过，未发现违规内容"

        high_count = sum(1 for v in violations if v["severity"] == "high")
        medium_count = sum(1 for v in violations if v["severity"] == "medium")
        low_count = sum(1 for v in violations if v["severity"] == "low")

        report = []
        report.append("📋 合规检查报告")
        report.append("=" * 50)
        report.append(f"总违规数: {len(violations)}")
        report.append(f"  高风险: {high_count} 个")
        report.append(f"  中风险: {medium_count} 个")
        report.append(f"  低风险: {low_count} 个")
        report.append("")

        if high_count > 0:
            report.append("🔴 高风险违规:")
            for v in violations:
                if v["severity"] == "high":
                    turn_info = f"第{v['turn']}轮: " if "turn" in v else ""
                    report.append(f"  - [{v['rule_id']}] {v['description']}")
                    if v['matched_text']:
                        report.append(f"    匹配内容: {v['matched_text']}")
                    report.append(f"    建议: {v['suggestion']}")
                    if "text" in v:
                        report.append(f"    原文: {v['text']}")
                    report.append("")

        if medium_count > 0:
            report.append("🟠 中风险违规:")
            for v in violations:
                if v["severity"] == "medium":
                    turn_info = f"第{v['turn']}轮: " if "turn" in v else ""
                    report.append(f"  - [{v['rule_id']}] {v['description']}")
                    if v['matched_text']:
                        report.append(f"    匹配内容: {v['matched_text']}")
                    report.append(f"    建议: {v['suggestion']}")
                    if "text" in v:
                        report.append(f"    原文: {v['text']}")
                    report.append("")

        if low_count > 0:
            report.append("🟡 低风险提示:")
            for v in violations:
                if v["severity"] == "low":
                    turn_info = f"第{v['turn']}轮: " if "turn" in v else ""
                    report.append(f"  - [{v['rule_id']}] {v['description']}")
                    report.append(f"    建议: {v['suggestion']}")
                    if "text" in v:
                        report.append(f"    原文: {v['text']}")
                    report.append("")

        if high_count > 0:
            report.append("❌ 总体结论: 不合规，存在高风险违规内容，禁止上线使用")
        elif medium_count > 0:
            report.append("⚠️  总体结论: 存在中风险违规内容，建议优化后上线")
        else:
            report.append("✅ 总体结论: 基本合规，低风险内容可选择性优化")

        return "\n".join(report)


# 全局实例
_compliance_checker = None


def get_compliance_checker() -> ComplianceChecker:
    """获取全局合规检查器实例"""
    global _compliance_checker
    if _compliance_checker is None:
        _compliance_checker = ComplianceChecker()
    return _compliance_checker


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="合规检查工具")
    parser.add_argument("--text", help="检查单个文本的合规性")
    parser.add_argument("--file", help="检查对话日志文件的合规性")

    args = parser.parse_args()

    checker = get_compliance_checker()

    if args.text:
        print(f"检查文本: {args.text}")
        is_ok, violations = checker.check(args.text)
        print(checker.generate_report(violations))
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and "agent" in data[0]:
            is_ok, violations = checker.check_conversation(data)
        elif isinstance(data, dict) and "turns" in data:
            turns = [{"agent": t["agent"], "customer": t["customer"]} for t in data["turns"]]
            is_ok, violations = checker.check_conversation(turns)
        else:
            print("不支持的文件格式")
            sys.exit(1)
        print(checker.generate_report(violations))
    else:
        # 测试
        test_texts = [
            "Kamu harus bayar sekarang, jika tidak saya akan datang ke rumah kamu.",
            "Bapak jangan khawatir, kami hanya menanyakan kapan bisa membayar tagihan.",
            "Anjing! Kamu pikir bisa kabur dari hutang?",
            "Pak, jika kamu bayar hari ini, kami akan berikan diskon 50%."
        ]

        for text in test_texts:
            print("="*70)
            print(f"测试文本: {text}")
            is_ok, violations = checker.check(text)
            print(checker.generate_report(violations))
            print("\n")
