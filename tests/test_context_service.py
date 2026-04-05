import unittest

from memory.context_service import ContextService
from memory.long_term import LongTermMemoryItem


class FakeSnapshot:
    def __init__(self, values):
        self.values = values


class FakeAgent:
    def get_state(self, _config):
        return FakeSnapshot(
            {
                "messages": [
                    {"role": "user", "content": "上轮我让你查北京地区资源"},
                    {"role": "assistant", "content": "我已经定位到北京地区资源问题。"},
                ]
            }
        )


class FakeLongTermStore:
    def __init__(self):
        self.written = []

    def search(self, query, user_id, limit=5):
        del user_id
        del limit
        return [
            LongTermMemoryItem(text="张三负责北京地区铁塔资源问题", metadata={}),
            LongTermMemoryItem(text="张三偏好先给结论，再给依据", metadata={}),
            LongTermMemoryItem(text=f"与当前问题相关：{query}", metadata={}),
        ]

    def write_memories(self, user_id, memories, metadata=None):
        self.written.append((user_id, memories, metadata))
        return memories


class ContextServiceTests(unittest.TestCase):
    def test_build_runtime_context_merges_short_and_long_term(self):
        service = ContextService(
            long_term_store=FakeLongTermStore(),
            checkpoint_ns="test-ns",
            context_max_items=3,
            context_max_chars=300,
            short_term_limit=4,
        )
        bundle = service.build_runtime_context(
            agent=FakeAgent(),
            user_id="zhangsan",
            thread_id="thread-1",
            user_input="请按我的偏好总结北京地区问题",
        )
        self.assertIn("短期上下文", bundle.compressed_context)
        self.assertIn("长期记忆", bundle.compressed_context)
        self.assertEqual(len(bundle.mem0_memories), 3)

    def test_write_memory_after_turn_uses_filtered_candidates(self):
        store = FakeLongTermStore()
        service = ContextService(long_term_store=store)
        written = service.write_memory_after_turn(
            user_id="zhangsan",
            thread_id="thread-1",
            user_input="请记住：我是平台创新中心的张三。以后回答请先给结论，再给依据。",
            assistant_response="已记住。",
        )
        self.assertEqual(len(written), 2)
        self.assertEqual(store.written[0][0], "zhangsan")


if __name__ == "__main__":
    unittest.main()
