import unittest
from unittest import mock

from memory.short_term import build_checkpoint_config, get_short_term_context, open_postgres_checkpointer


class FakeSnapshot:
    def __init__(self, values):
        self.values = values


class FakeAgent:
    def get_state(self, _config):
        return FakeSnapshot(
            {
                "messages": [
                    {"role": "system", "content": "<external_context>\nignored\n</external_context>"},
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "你好，我可以帮你查资源"},
                ]
            }
        )


class FakeCheckpointer:
    def __init__(self) -> None:
        self.setup_called = False

    def setup(self) -> None:
        self.setup_called = True


class FakeCheckpointerContextManager:
    def __init__(self, saver):
        self.saver = saver

    def __enter__(self):
        return self.saver

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePostgresSaver:
    last_conn_string = None

    @classmethod
    def from_conn_string(cls, conn_string):
        cls.last_conn_string = conn_string
        return FakeCheckpointerContextManager(FakeCheckpointer())


class ShortTermCheckpointTests(unittest.TestCase):
    def test_build_checkpoint_config(self):
        config = build_checkpoint_config("thread-1", "ns-1")
        self.assertEqual(config["configurable"]["thread_id"], "thread-1")
        self.assertEqual(config["configurable"]["checkpoint_ns"], "ns-1")

    def test_get_short_term_context_filters_external_system_context(self):
        context = get_short_term_context(FakeAgent(), "thread-1", "ns-1", limit=5)
        self.assertIn("用户：你好", context.summary)
        self.assertNotIn("ignored", context.summary)

    def test_open_postgres_checkpointer_runs_setup(self):
        with mock.patch("memory.short_term.PostgresSaver", FakePostgresSaver):
            with open_postgres_checkpointer("postgresql://demo", auto_setup=True) as saver:
                self.assertTrue(saver.setup_called)
        self.assertEqual(FakePostgresSaver.last_conn_string, "postgresql://demo")


if __name__ == "__main__":
    unittest.main()
