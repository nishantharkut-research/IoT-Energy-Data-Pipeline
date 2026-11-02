from dashboard.app import _show_row


def test_dashboard_does_not_display_retired_energy_estimates() -> None:
    class Display:
        messages: list[str] = []

        def info(self, message: str) -> None:
            self.messages.append(message)

        def columns(self, count: int):
            raise AssertionError("retired energy estimates must not reach metrics")

    display = Display()
    _show_row(
        display,
        "energy_quality",
        {
            "absolute_kwh_discrepancy": "2",
            "affected_meter_periods": 2,
            "tariff_scenarios": [{"gross_exposure": "2"}],
        },
    )
    assert len(display.messages) == 1
    assert "reanalysis" in display.messages[0]
