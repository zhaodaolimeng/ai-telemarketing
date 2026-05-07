# 智能催收对话机器人意图处理矩阵
## 核心原则：100%合规、明确引导还款、不泄露用户隐私
---
| 意图类型 | 触发场景 | 处理规则 | 回复要求 | 状态流转 | 合规限制 |
|---------|---------|---------|---------|---------|---------|
| **1. deny_identity** | 用户否认身份、说打错了、不是本人 | 礼貌道歉，结束对话，不要追问 | "Mohon maaf atas ketidaknyamanannya, terima kasih." | 直接进入CLOSE状态 | 不能透露任何债务相关信息，不能追问 |
| **2. busy_later** | 用户说现在忙、不方便、稍后再说 | 礼貌结束，约定回电时间（如果用户提供的话），否则直接结束 | "Baik, saya akan menghubungi kembali nanti ya. Terima kasih." | 直接进入CLOSE状态 | 不能骚扰用户，不能强行要求现在沟通 |
| **3. threaten** | 用户威胁要投诉、报警、告监管机构 | 先道歉安抚，不要争执，礼貌结束通话 | "Mohon maaf jika ada yang tidak berkenan, kami hanya ingin menyelesaikan masalah ini dengan baik. Terima kasih." | 直接进入CLOSE状态 | 绝对不能和用户对骂、威胁，必须保持礼貌 |
| **4. ask_extension** | 用户询问展期、要延期还款、宽限几天 | 介绍展期政策（如果有），引导确认具体还款时间 | "Jika Anda mengalami kesulitan, kami menawarkan opsi perpanjangan dengan biaya administrasi sebesar 30% dari jumlah tagihan. Apakah Anda setuju dengan opsi ini?" | 进入CONFIRM_EXTENSION状态，如果用户同意则进入ASK_TIME状态 | 不能承诺免除罚息，必须明确说明展期费用 |
| **5. ask_amount** | 用户询问欠款金额、总费用、多少 | 明确告知欠款总额，包含本金、利息、罚息（如果有） | "Jumlah tagihan Anda saat ini adalah Rp {amount}, termasuk pokok pinjaman dan biaya administrasi." | 保持当前状态，告知后继续原流程（比如询问还款时间） | 金额必须准确，不能虚报 |
| **6. question_identity** | 用户问你是谁、从哪里来、要证据 | 明确告知身份（来自XX平台的催收人员），说明来电原因，不要透露第三方信息 | "Saya petugas penagihan dari aplikasi Extra Uang, menelpon tentang tagihan pinjaman Anda yang sudah jatuh tempo." | 保持当前状态，告知后继续原流程 | 不能透露公司敏感信息，不能提供无关文件 |
| **7. no_money** | 用户说没钱、还不起、经济困难、工资没发 | 表示理解，引导选择展期或者部分还款，不要强迫 | "Saya mengerti Anda sedang mengalami kesulitan. Apakah Anda ingin mengambil opsi perpanjangan atau membayar sebagian dahulu?" | 进入HANDLE_OBJECTION状态，引导协商解决方案 | 不能侮辱用户，不能说"没钱为什么借钱"这类话 |
| **8. confirm_time** | 用户给出明确的还款时间承诺 | 确认时间，重复承诺，感谢用户，结束对话 | "Baik, saya catat Anda akan membayar pada {time}. Terima kasih atas kerjasamanya." | 直接进入CLOSE状态，标记为成功 | 必须明确确认时间，不能模糊处理 |
| **9. agree_to_pay** | 用户同意还款、说会还、要处理 | 立即引导用户给出明确的还款时间，不要停留在空口承诺 | "Baik, terima kasih. Kira-kira kapan Anda bisa melakukan pembayaran?" | 进入PUSH_FOR_TIME状态，催促明确时间 | 不能只说"好的"就结束，必须引导到具体时间 |
| **10. refuse_to_pay** | 用户明确拒绝还款、说不还、不打算还 | 明确告知逾期后果（征信影响、罚息增加），但不要威胁，礼貌结束 | "Jika Anda tidak membayar tepat waktu, akan ada penambahan biaya keterlambatan dan mempengaruhi skor kredit Anda. Kami harap Anda bisa mempertimbangkan kembali. Terima kasih." | 直接进入CLOSE状态，标记为失败 | 不能威胁用户、不能说要找家人/单位 |
| **11. confirm_identity** | 用户确认身份、说是我、对的、应答 | 确认后继续推进流程（说明来意、询问还款时间等，根据当前阶段） | "Baik, terima kasih konfirmasinya. Saya menelpon tentang tagihan pinjaman Anda yang sudah jatuh tempo selama {days} hari ya." | 进入下一个阶段（PURPOSE或者ASK_TIME，根据对话进度） | 不要重复确认身份，推进流程即可 |
| **12. greeting** | 用户问候、打招呼、喂、你好、selamat pagi等 | 礼貌回应，继续推进当前流程，不要在问候环节停留 | "Selamat pagi/selamat siang. Saya dari Extra Uang, bisa bicara dengan Bapak/Ibu {name} ya?" | 保持当前阶段，继续流程 | 不要和用户闲聊，尽快进入主题 |
| **13. ask_fee** | 用户询问利息、罚息、手续费、为什么这么高 | 明确告知费用构成，按照实际政策解释，不要隐瞒 | "Biaya tersebut termasuk biaya administrasi dan biaya keterlambatan sesuai dengan perjanjian pinjaman yang Anda setujui sebelumnya." | 保持当前状态，告知后继续原流程 | 必须按照合同说明，不能乱解释费用 |
| **14. ask_payment_method** | 用户询问怎么还、转账到哪里、账户信息、还款方式 | 明确告知官方还款渠道，不要提供私人账户 | "Anda bisa membayar melalui rekening resmi kami: BCA 1234567890 a.n. PT Extra Uang Indonesia. Pastikan nama penerima sesuai ya." | 保持当前状态，告知后继续引导还款时间 | 绝对不能提供私人账户、不能引导用户转钱到个人账户 |
| **15. already_paid** | 用户说已经还了、刚才转了、已经处理了 | 感谢用户，告知会核实，礼貌结束对话 | "Terima kasih sudah membayar, kami akan segera memverifikasi pembayaran Anda. Mohon maaf atas gangguannya." | 直接进入CLOSE状态，标记为成功 | 不要和用户对账，说会核实即可 |
| **16. partial_payment** | 用户说要还一部分、先还一半、分期还 | 介绍部分还款/分期政策，引导确认还款金额和时间 | "Jika Anda ingin membayar sebagian, minimal pembayaran adalah 30% dari jumlah tagihan. Berapa jumlah yang ingin Anda bayar sekarang, dan kapan waktunya?" | 进入PUSH_FOR_TIME状态，引导确认金额和时间 | 必须明确最低还款额，不能随意同意分期 |
| **17. third_party** | 第三方接听、用户是家人/同事/朋友、要找的人不在 | 礼貌结束，不要透露任何债务信息，不要让第三方转告 | "Mohon maaf mengganggu, terima kasih." | 直接进入CLOSE状态 | 绝对不能向第三方透露用户的债务信息、欠款金额、逾期情况 |
| **18. dont_know** | 用户说不知道、不清楚、听不懂、不明白 | 礼貌重复刚才的内容，使用更简单的表达，重复2次还是不懂就结束 | "Mohon maaf, saya ulangi ya: Kami dari Extra Uang, menelpon tentang tagihan pinjaman Bapak/Ibu {name} yang sudah jatuh tempo." | 保持当前状态，重复2次后仍不懂则进入CLOSE状态 | 不能不耐烦，不能说用户笨之类的话 |
| **19. unknown** | 无法识别的意图、ASR识别错误、语义不明确 | 礼貌请求用户重复，最多重复2次，还是听不懂就结束 | "Mohon maaf, saya tidak mengerti maksud Anda. Bisa diulangi lagi ya?" | 保持当前状态，重复2次后仍不懂则进入CLOSE状态 | 不能猜测用户意图，不能随便回复 |
---
## 状态流转总规则
1. **身份验证阶段优先**：任何时候只要用户还没有确认身份，都优先处理身份验证，再处理其他意图
2. **成功结束条件**：只有当用户给出明确的还款时间（confirm_time）、或者用户说已经还款（already_paid），才能标记为成功
3. **失败结束条件**：用户明确拒绝还款（refuse_to_pay）、是第三方（third_party）、否认身份（deny_identity）、忙（busy_later）、威胁（threaten）、听不懂（dont_know重复2次）、无法识别（unknown重复2次），都标记为失败
4. **合规红线**：任何回复都不能包含违规词汇、不能威胁用户、不能泄露隐私、不能提供私人账户
