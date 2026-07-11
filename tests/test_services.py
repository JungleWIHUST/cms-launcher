import unittest

from services import Service, SERVICE_MAP, SERVICES


class ServicesTest(unittest.TestCase):
    def test_service_registry_contains_expected_services(self) -> None:
        names = {service.config.executable for service in SERVICES}
        self.assertIn("cmsWorker", names)
        self.assertIn("cmsAdminWebServer", names)
        self.assertIn("cmsRankingWebServer", names)

    def test_runtime_service_defaults(self) -> None:
        service = Service(SERVICES[0])
        self.assertIsNone(service.pid)
        self.assertFalse(service.running)
        self.assertEqual(service.restart_count, 0)
        self.assertIn("cms", str(service.log_file))

    def test_service_map_contains_worker(self) -> None:
        self.assertIn("cmsWorker", SERVICE_MAP)


if __name__ == "__main__":
    unittest.main()
