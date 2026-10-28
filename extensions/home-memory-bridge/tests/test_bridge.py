from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import httpx

from home_bridge.server import create_app
from home_bridge.store import (
    add_note,
    forget_note,
    get_api_key,
    init,
    list_notes,
    memory_context,
    recent,
    recording,
    search,
    set_recording,
)


class BridgeTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        init(self.root)
        self.requests = []

        def upstream(request):
            if request.url.path == '/v1/models':
                return httpx.Response(200, json={'data': [{'id': 'home-qwen'}], 'object': 'list'})
            assert request.url.path == '/v1/chat/completions'
            body = json.loads(request.content)
            self.requests.append(body)
            if body.get('stream'):
                events = [
                    {'choices': [{'delta': {'content': 'Hello'}}]},
                    {'choices': [{'delta': {'content': ' again.'}}]},
                ]
                raw = ''.join('data: ' + json.dumps(x) + '\n\n' for x in events) + 'data: [DONE]\n\n'
                return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=raw.encode())
            return httpx.Response(200, json={'choices': [{'message': {'role': 'assistant', 'content': 'That was Violet Comet.'}}]})

        self.app = create_app(self.root, httpx.MockTransport(upstream), 'http://llama.mock/v1')
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://home.test',
                                        headers={'Authorization': 'Bearer ' + get_api_key(self.root)})

    async def asyncTearDown(self):
        await self.client.aclose()
        self.temp.cleanup()

    async def test_conversation_persists_and_is_retrieved_in_new_chat(self):
        first = await self.client.post('/v1/chat/completions', json={
            'model': 'home-qwen', 'messages': [
                {'role': 'system', 'content': 'You are AIRI.'},
                {'role': 'user', 'content': 'My experiment is called Violet Comet.'},
            ]})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(recent(self.root)), 1)
        second = await self.client.post('/v1/chat/completions', json={
            'model': 'home-qwen', 'messages': [{'role': 'user', 'content': 'What was my experiment called?'}]})
        self.assertEqual(second.status_code, 200)
        injected = [m for m in self.requests[1]['messages'] if m['role'] == 'system']
        self.assertIn('Violet Comet', '\n'.join(m['content'] for m in injected))
        self.assertEqual(len(recent(self.root)), 2)

    async def test_streamed_chat_is_forwarded_and_saved(self):
        response = await self.client.post('/v1/chat/completions', json={
            'model': 'home-qwen', 'stream': True, 'messages': [{'role': 'user', 'content': 'Hello'}]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('data: [DONE]', response.text)
        self.assertEqual(recent(self.root)[0]['assistant_text'], 'Hello again.')

    async def test_paused_mode_does_not_inject_or_save_history(self):
        set_recording(self.root, False)
        self.assertFalse(recording(self.root))
        response = await self.client.post('/v1/chat/completions', json={
            'model': 'home-qwen', 'messages': [{'role': 'user', 'content': 'Hi'}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.requests[0]['messages'], [{'role': 'user', 'content': 'Hi'}])
        self.assertEqual(recent(self.root), [])

    async def test_auth_required_and_models_passthrough(self):
        noauth = await self.client.get('/v1/models', headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(noauth.status_code, 401)
        good = await self.client.get('/v1/models')
        self.assertEqual(good.json()['data'][0]['id'], 'home-qwen')

    async def test_saved_notes_and_forgetting(self):
        idx = add_note(self.root, 'Never interrupt a competitive CS match for trivia.')
        self.assertIn('competitive CS', list_notes(self.root)[0]['text'])
        matches = search(self.root, 'competitive CS', 'notes')
        self.assertEqual(matches[0]['id'], idx)
        self.assertTrue(forget_note(self.root, idx))
        self.assertEqual(search(self.root, 'competitive CS', 'notes'), [])

    async def test_multimodal_data_is_not_recorded(self):
        response = await self.client.post('/v1/chat/completions', json={
            'model': 'home-qwen', 'messages': [{'role': 'user', 'content': [
                {'type': 'text', 'text': 'What is this?'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,supersecret'}}
            ]}]})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('supersecret', recent(self.root)[0]['user_text'])
        self.assertIn('supersecret', str(self.requests[0]['messages']))  # forwarded to model as-is


if __name__ == '__main__':
    unittest.main()
