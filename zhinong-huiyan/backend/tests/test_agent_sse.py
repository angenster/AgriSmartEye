"""SSE 诊断流：事件顺序与异常终态。不加载真实模型，run_agent 用桩替代。"""
import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from agent.planner import StepRecord
from routers import agent as agent_router
from routers.auth import get_current_user

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def _record(no: int) -> StepRecord:
    return StepRecord(
        step_no=no,
        thought=f"第 {no} 步",
        tool_name="run_cnn_detect",
        tool_args={},
        result={"ok": True, "data": {"disease": "芒果炭疽病"}},
        step_id=no,
    )


def _fake_run_agent(db, image_path, user_id=None, field_id=None,
                    trigger="upload", on_step=None):
    on_step(_record(1))
    on_step(_record(2))
    return {
        "run_id": 1,
        "status": "done",
        "steps_used": 2,
        "report": {},
        "evidence_valid": True,
        "evidence_problems": [],
        "steps": [],
    }


def _boom(db, image_path, user_id=None, field_id=None,
          trigger="upload", on_step=None):
    raise RuntimeError("模拟失败")


class AgentSSETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
        self._orig = agent_router.run_agent

    def tearDown(self):
        main.app.dependency_overrides.clear()
        agent_router.run_agent = self._orig

    def _stream(self):
        with self.client.stream(
            "POST",
            "/api/v1/agent/diagnose/stream",
            files={"file": ("test.png", PNG_BYTES, "image/png")},
        ) as resp:
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.headers["content-type"].startswith("text/event-stream"))
            return "".join(resp.iter_text())

    def test_event_order(self):
        agent_router.run_agent = _fake_run_agent
        body = self._stream()
        events = [ln[6:].strip() for ln in body.splitlines() if ln.startswith("event:")]
        self.assertEqual(events, ["start", "step", "step", "report", "done"])
        self.assertIn('"tool_name": "run_cnn_detect"', body)

    def test_error_then_done(self):
        agent_router.run_agent = _boom
        body = self._stream()
        events = [ln[6:].strip() for ln in body.splitlines() if ln.startswith("event:")]
        self.assertEqual(events, ["start", "error", "done"])
        self.assertIn("模拟失败", body)

    def test_rejects_non_image(self):
        resp = self.client.post(
            "/api/v1/agent/diagnose/stream",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
