# 测试样例怎么先做

评测套件 `eval/fixtures/suite-v1` **不是** 单元测试样例。那是 13 道策略对比题，太重，也绑着检索策略。测试样例要更小：一条规则、一次失败、一个断言。

下面几种做法都能「先弄样例」。Arbor 现在采用 **1 + 2**，样例已放在 `tests/examples/`。

## 方式对比

| 方式 | 做什么 | 适合 | 现在不要 |
|---|---|---|---|
| **1. Given-When-Then YAML** | 每条规则写成可加载规格 | 领域 / 应用 P0 | — |
| **2. 从金标裁剪 mini 世界** | 两租户、两个人设、几条记忆 | 契约测、隔离 | 把整份 suite-v1 当单测夹具 |
| **3. 先写会红的 pytest** | `assert` + 尚未实现 | 开始写 `src/` 的当天 | 现在还没有领域模块 |
| **4. 对象工厂** | `PersonaFactory.linxia()` | 代码落地后减少重复 | 先不要为工厂写工厂 |
| **5. 表驱动 / parametrize** | 同一测试跑多行数据 | YAML 转 pytest 时 | — |
| **6. 性质测试（Hypothesis）** | 「任意两租户都不泄漏」 | 过滤函数稳定之后 | 第一周 |
| **7. OpenAPI example** | HTTP 请求/响应样例 | API 层 | 当领域测试 |
| **8. 录制真实对话** | 线上或手工聊完回放 | 回归 | 没有系统时录了也无处断言 |

Gherkin/Cucumber、Postman 大集合、用 RAGAS 当单测，都不适合当第一批样例：重、慢、测错层。

## 推荐路径（就按这个做）

```text
现在     写 YAML 样例（本目录）——人读、机器以后也能读
接着     生成代码时：pytest 读这些 YAML，或一对一抄成 test_*.py
契约层   加载 tests/fixtures/mini-world.yaml 进 Postgres
评测层   继续只用 eval/fixtures/suite-v1，不要混进 pytest 领域测
```

一条样例只断言 **一个行为**。不要在领域样例里写「Recall@5」；那是评测。

## YAML 约定

```yaml
id: domain.persona.tenant_immutable
layer: domain          # domain | application | contract | api
severity: p0
given: { ... }
when:  { ... }
then:  { ... }
```

- `layer` 决定以后测试放哪一层、用不用 Postgres / Fake LLM。
- ID 与 [testing.md](testing.md) §5 清单对应，生成代码后 pytest 名字应对得上。
- `then.error` 用稳定错误码，不要对中文消息做精确匹配。

## 样例文件

| 文件 | 层 |
|---|---|
| [tests/examples/domain.yaml](../tests/examples/domain.yaml) | 不变式 |
| [tests/examples/application.yaml](../tests/examples/application.yaml) | 用例 + Fake 端口 |
| [tests/examples/contract.yaml](../tests/examples/contract.yaml) | pgvector 过滤 |
| [tests/examples/api.yaml](../tests/examples/api.yaml) | HTTP |
| [tests/fixtures/mini-world.yaml](../tests/fixtures/mini-world.yaml) | 契约/应用共用的最小世界 |

mini-world 的 ID 可以和 suite-v1 同源（方便你脑子里只有一套林夏），但 **条目更少**，且不含评测题。

## 转成 pytest 时怎么接（实现时）

不要手写第二份期望。例如：

```text
@pytest.mark.parametrize("case", load_yaml("tests/examples/domain.yaml"))
def test_domain_examples(case):
    # 按 case.when.action 调领域方法
    ...
```

应用层样例里的 `then.llm_prompt_must_not_contain` 断言 Fake LLM 记录的上下文，不断言 DeepSeek 文风。

## 明确不要的样例

- 「跟林夏随便聊两句看看聪不聪明」
- 没有 `forbidden` 的开放生成题
- 用 mock 掉 `AuthorizationPolicy` 的聊天样例
- 把 suite-v1 的 13 题原样复制进 `tests/unit`
