import unittest

from process_manager import ProcessManager
from services import Service, SERVICE_MAP, SERVICES
from config import ServiceConfig


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

    def test_collect_statuses_returns_runtime_fields(self) -> None:
        manager = ProcessManager(logger=None)
        service = Service(ServiceConfig(name="Demo", executable="cmsDemo"))
        service.status = "RUNNING"
        service.pid = 12345
        service.cpu_usage = 12.5
        service.ram_usage = 2048
        service.restart_count = 2
        service.exit_code = 0
        manager.services = {"cmsDemo": service}

        snapshot = manager.collect_statuses()[0]
        self.assertEqual(snapshot["name"], "Demo")
        self.assertEqual(snapshot["status"], "RUNNING")
        self.assertEqual(snapshot["pid"], 12345)
        self.assertEqual(snapshot["cpu"], 12.5)
        self.assertEqual(snapshot["ram"], 2048)
        self.assertEqual(snapshot["restart_count"], 2)
        self.assertEqual(snapshot["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
