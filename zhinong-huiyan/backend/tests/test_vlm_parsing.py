"""VLM 返回解析：纯 JSON、markdown 围栏、前后夹杂说明文字。"""
import unittest

from agent.tools import _parse_vlm_json


class VlmParsingTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_parse_vlm_json('{"disease": "芒果炭疽病"}')["disease"], "芒果炭疽病")

    def test_fenced_json(self):
        text = '```json\n{"disease": "芒果白粉病", "confidence": 0.8}\n```'
        self.assertEqual(_parse_vlm_json(text)["disease"], "芒果白粉病")

    def test_json_with_prose(self):
        text = '判断如下：\n{"disease": "健康", "confidence": 0.9}\n以上。'
        self.assertEqual(_parse_vlm_json(text)["disease"], "健康")

    def test_invalid_raises(self):
        with self.assertRaises(Exception):
            _parse_vlm_json("not json")


if __name__ == "__main__":
    unittest.main()
