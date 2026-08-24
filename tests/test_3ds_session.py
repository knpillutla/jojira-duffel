import sys, os
sys.path.insert(0, os.path.abspath('.'))
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.duffel.api.app import app


class Test3dSecureSession(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('src.duffel.api.routes.get_duffel_client')
    def test_generate_client_component_key(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.flights.create_component_client_key.return_value = {
            'client_key': 'client_000000000000000000000000',
            'component_client_key': 'client_000000000000000000000000',
            'live_mode': False,
            'created_at': '2026-08-24T08:00:00'
        }

        response = self.client.post('/api/v1/payments/component-client-key')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['client_key'].startswith('client_'))
        print('\n[TEST PASS] Client Component Key endpoint returned valid client_key:', data['client_key'])

    @patch('src.duffel.api.routes.get_duffel_client')
    def test_generate_3ds_session_returns_server_to_server_id(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.flights.create_three_d_secure_session.return_value = {
            'three_d_secure_session_id': '3ds_000000000000000000000001',
            'id': '3ds_000000000000000000000001',
            'status': 'ready_for_payment',
            'created_at': '2026-08-24T08:00:00'
        }

        response = self.client.post('/api/v1/payments/three_d_secure_sessions', json={
            'card_id': 'car_000000000000000000000001',
            'amount': '148.00',
            'currency': 'USD'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['three_d_secure_session_id'], '3ds_000000000000000000000001')
        self.assertEqual(data['id'], '3ds_000000000000000000000001')
        self.assertEqual(len(data['three_d_secure_session_id']), 28)
        self.assertEqual(data['status'], 'ready_for_payment')
        print('\n[TEST PASS] 3D Secure Session controller returned server-to-server ID:', data['three_d_secure_session_id'])

if __name__ == '__main__':
    unittest.main()
