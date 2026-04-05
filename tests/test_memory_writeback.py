import unittest

from memory.long_term import (
    extract_long_term_memory_items,
    is_long_term_memory_candidate,
    normalize_mem0_config,
)


class MemoryWritebackTests(unittest.TestCase):
    def test_extracts_explicit_long_term_preferences(self):
        items = extract_long_term_memory_items(
            user_input="请记住：我是平台创新中心的张三。以后回答请先给结论，再给依据。",
            assistant_response="好的。",
        )
        self.assertIn("我是平台创新中心的张三", items)
        self.assertIn("以后回答请先给结论，再给依据", items)

    def test_rejects_transient_or_sensitive_text(self):
        self.assertFalse(is_long_term_memory_candidate("本次工单号是 T123456"))
        self.assertFalse(is_long_term_memory_candidate("我的 API_KEY 是 abc"))
        self.assertFalse(is_long_term_memory_candidate("资源编码 00135100000000013123839"))

    def test_normalizes_siliconflow_mem0_config(self):
        config = {
            "llm": {
                "provider": "siliconflow",
                "config": {"model": "Qwen/Qwen3-14B", "api_key": "test-key"},
            },
            "embedder": {
                "provider": "siliconflow",
                "config": {"model": "Qwen/Qwen3-Embedding-4B", "api_key": "test-key"},
            },
            "reranker": {
                "provider": "siliconflow",
                "config": {"model": "Qwen/Qwen3-Reranker-4B", "api_key": "test-key"},
            },
        }

        normalized = normalize_mem0_config(config)

        self.assertEqual(normalized["llm"]["provider"], "openai")
        self.assertEqual(normalized["embedder"]["provider"], "openai")
        self.assertEqual(
            normalized["llm"]["config"]["openai_base_url"],
            "https://api.siliconflow.cn/v1",
        )
        self.assertEqual(
            normalized["embedder"]["config"]["openai_base_url"],
            "https://api.siliconflow.cn/v1",
        )
        self.assertIsNone(normalized["reranker"])


if __name__ == "__main__":
    unittest.main()
