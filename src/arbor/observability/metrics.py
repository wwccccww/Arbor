from __future__ import annotations

from dataclasses import dataclass, field

from arbor.observability.labels import validate_metric_labels

_ARBOR_PROMETHEUS_METRICS: object | None = None
_ARBOR_PROMETHEUS_REGISTRY: object | None = None


@dataclass
class MetricsRegistry:
    enabled: bool = True
    counters: dict[tuple[str, tuple[str, ...]], float] = field(default_factory=dict)
    histograms: dict[tuple[str, tuple[str, ...]], list[float]] = field(default_factory=dict)
    gauges: dict[tuple[str, tuple[str, ...]], float] = field(default_factory=dict)

    def _key(self, name: str, labels: dict[str, str]) -> tuple[str, tuple[str, ...]]:
        clean = validate_metric_labels(labels)
        label_key = tuple(f"{k}={v}" for k, v in sorted(clean.items()))
        return name, label_key

    def increment(self, name: str, value: float = 1, **labels: str) -> None:
        if not self.enabled:
            return
        key = self._key(name, labels)
        self.counters[key] = self.counters.get(key, 0.0) + value

    def observe(self, name: str, value: float, **labels: str) -> None:
        if not self.enabled:
            return
        key = self._key(name, labels)
        self.histograms.setdefault(key, []).append(value)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        if not self.enabled:
            return
        key = self._key(name, labels)
        self.gauges[key] = value


def prometheus_registry() -> object | None:
    return _ARBOR_PROMETHEUS_REGISTRY


def build_prometheus_registry() -> MetricsRegistry | object:
    global _ARBOR_PROMETHEUS_METRICS, _ARBOR_PROMETHEUS_REGISTRY
    if _ARBOR_PROMETHEUS_METRICS is not None:
        return _ARBOR_PROMETHEUS_METRICS
    try:
        from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

        registry = CollectorRegistry(auto_describe=True)
        _ARBOR_PROMETHEUS_REGISTRY = registry

        class _PrometheusMetrics:
            def __init__(self) -> None:
                self._counters: dict[str, Counter] = {}
                self._histograms: dict[str, Histogram] = {}
                self._gauges: dict[str, Gauge] = {}

            def _labels(self, labels: dict[str, str]) -> dict[str, str]:
                return validate_metric_labels(labels)

            def increment(self, name: str, value: float = 1, **labels: str) -> None:
                clean = self._labels(labels)
                metric = self._counters.get(name)
                if metric is None:
                    metric = Counter(
                        name,
                        name,
                        labelnames=tuple(sorted(clean.keys())),
                        registry=registry,
                    )
                    self._counters[name] = metric
                if clean:
                    metric.labels(**clean).inc(value)
                else:
                    metric.inc(value)

            def observe(self, name: str, value: float, **labels: str) -> None:
                clean = self._labels(labels)
                metric = self._histograms.get(name)
                if metric is None:
                    metric = Histogram(
                        name,
                        name,
                        labelnames=tuple(sorted(clean.keys())),
                        registry=registry,
                    )
                    self._histograms[name] = metric
                if clean:
                    metric.labels(**clean).observe(value)
                else:
                    metric.observe(value)

            def set_gauge(self, name: str, value: float, **labels: str) -> None:
                clean = self._labels(labels)
                metric = self._gauges.get(name)
                if metric is None:
                    metric = Gauge(
                        name,
                        name,
                        labelnames=tuple(sorted(clean.keys())),
                        registry=registry,
                    )
                    self._gauges[name] = metric
                if clean:
                    metric.labels(**clean).set(value)
                else:
                    metric.set(value)

        _ARBOR_PROMETHEUS_METRICS = _PrometheusMetrics()
        return _ARBOR_PROMETHEUS_METRICS
    except ImportError:
        return MetricsRegistry()
