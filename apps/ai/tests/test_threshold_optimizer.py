import numpy as np
import pytest

from src.components.threshold_optimizer import ThresholdOptimizer, ThresholdResult


def test_threshold_optimizer_validation():
    with pytest.raises(ValueError, match="min_recall must be between 0 and 1"):
        ThresholdOptimizer(min_recall=1.5)

    with pytest.raises(ValueError, match="thresholds must be between 0 and 1"):
        ThresholdOptimizer(thresholds=np.array([-0.1, 0.5, 1.2]))


def test_threshold_optimizer_optimize_success():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
    # 양성에 대해 높은 확률값 부여
    y_prob = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95])

    optimizer = ThresholdOptimizer(min_recall=0.8, thresholds=np.arange(0.1, 0.9, 0.1))
    result = optimizer.optimize(y_true, y_prob)

    assert isinstance(result, ThresholdResult)
    assert result.recall >= 0.8
    assert 0.0 <= result.threshold <= 1.0
    assert 0.0 <= result.f1 <= 1.0


def test_threshold_optimizer_no_satisfying_recall():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    # 양성 예측 확률이 모두 낮음
    y_prob = np.array([0.1, 0.1, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3])

    # 높은 min_recall(0.9)과 높은 임계값(0.5~0.9) 설정 시 만족하는 후보가 없음
    optimizer = ThresholdOptimizer(min_recall=0.9, thresholds=np.arange(0.5, 0.9, 0.1))
    with pytest.raises(ValueError, match="No threshold satisfies minimum recall"):
        optimizer.optimize(y_true, y_prob)


def test_threshold_optimizer_input_length_mismatch():
    optimizer = ThresholdOptimizer()
    with pytest.raises(ValueError, match="y_true and y_prob must have the same length"):
        optimizer.optimize(np.array([1, 0]), np.array([0.5]))


def test_threshold_optimizer_strategies():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95])

    opt_youden = ThresholdOptimizer(min_recall=0.5, strategy="youden_j")
    res_youden = opt_youden.optimize(y_true, y_prob)
    assert isinstance(res_youden, ThresholdResult)
    assert res_youden.specificity > 0

    opt_prec = ThresholdOptimizer(min_recall=0.5, strategy="precision")
    res_prec = opt_prec.optimize(y_true, y_prob)
    assert isinstance(res_prec, ThresholdResult)


def test_threshold_optimizer_fallback_mode():
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y_prob = np.array([0.1, 0.1, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3])

    optimizer = ThresholdOptimizer(
        min_recall=0.9,
        thresholds=np.arange(0.5, 0.9, 0.1),
        strict=False,
    )
    res = optimizer.optimize(y_true, y_prob)
    assert isinstance(res, ThresholdResult)
