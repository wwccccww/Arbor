# tests/examples

机器可加载的 Given-When-Then 样例，说明见 [docs/testing-examples.md](../../docs/testing-examples.md)。

领域层由 `tests/unit/domain/test_domain_examples.py` 直接读取 `domain.yaml`。应用 / HTTP / 契约 P0 在对应 pytest 文件中一对一落地，不要另起一套故事。
