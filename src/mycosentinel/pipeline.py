"""
Signal processing pipeline for MycoSentinel.
Handles noise filtering, normalization, and ML inference.
"""

import numpy as np
import time
from collections import deque
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not available, using fallback methods")

@dataclass
class ProcessedSignal:
    """Processed sensor signal with ML inference"""
    timestamp: float
    raw_value: float
    filtered_value: float
    normalized_value: float
    baseline: float
    anomaly_score: float
    contaminant_detected: bool
    confidence: float
    contaminant_type: Optional[str] = None
    concentration_estimate: Optional[float] = None

class SignalProcessor:
    """
    Real-time signal processing for biosensor data.
    
    Pipeline:
    1. Buffer recent readings
    2. Apply noise filtering (median, Kalman, or simple averaging)
    3. Normalize against baseline
    4. Anomaly detection
    5. ML classification (optional TensorFlow Lite)
    """
    
    def __init__(
        self,
        buffer_size: int = 60,  # 1 minute at 1Hz
        filter_type: str = "median",
        anomaly_threshold: float = 2.5,
        use_ml: bool = False,
        model_path: Optional[str] = None
    ):
        self.buffer = deque(maxlen=buffer_size)
        self.filter_type = filter_type
        self.anomaly_threshold = anomaly_threshold
        self.baseline = None
        self.baseline_std = 1.0
        self.use_ml = use_ml and TF_AVAILABLE
        self.model = None
        
        # Adaptive baseline parameters
        self.adaptation_rate = 0.01
        self.min_consecutive_anomaly = 5  # Seconds before trigger
        self._anomaly_counter = 0
        
        # Statistics tracking
        self.mean = 0.0
        self.var = 1.0
        self._count = 0
        
        # Load ML model if provided
        if self.use_ml and model_path:
            try:
                self.model = tf.lite.Interpreter(model_path=model_path)
                self.model.allocate_tensors()
                logger.info(f"TFLite model loaded: {model_path}")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.use_ml = False
        
        logger.info(f"SignalProcessor initialized (buffer={buffer_size}, filter={filter_type})")
    
    def _filter_signal(self, raw_value: float) -> float:
        """Apply noise filtering"""
        if self.filter_type == "median":
            if len(self.buffer) < 3:
                return raw_value
            # Simple median of recent values
            window = list(self.buffer)[-5:]
            if len(window) >= 3:
                return np.median(window)
            return np.mean(window) if window else raw_value
        
        elif self.filter_type == "ewma":
            # Exponentially weighted moving average
            if self._count == 0:
                return raw_value
            alpha = 0.3
            return alpha * raw_value + (1 - alpha) * self.mean
        
        else:  # simple
            return raw_value
    
    def _update_statistics(self, value: float):
        """Update running mean and variance (Welford's algorithm)"""
        self._count += 1
        delta = value - self.mean
        self.mean += delta / self._count
        delta2 = value - self.mean
        self.var = ((self._count - 1) * self.var + delta * delta2) / self._count
    
    def _calculate_anomaly_score(self, value: float) -> float:
        """Calculate anomaly score (Z-score)"""
        if self.baseline is None:
            return 0.0
        std = np.sqrt(self.var) if self.var > 0 else 1.0
        return abs(value - self.baseline) / std
    
    def calibrate_baseline(self, readings: List[float], duration_sec: int = 300):
        """Calibrate baseline from initialization period"""
        logger.info(f"Calibrating baseline from {len(readings)} samples...")
        
        self.baseline = np.mean(readings)
        self.baseline_std = np.std(readings)
        self.mean = self.baseline
        self.var = self.baseline_std ** 2
        
        self.buffer.extend(readings)
        
        logger.info(f"Baseline: {self.baseline:.4f} ± {self.baseline_std:.4f}")
    
    def process(self, raw_value: float, timestamp: Optional[float] = None) -> ProcessedSignal:
        """
        Process a new sensor reading through the full pipeline.
        """
        if timestamp is None:
            timestamp = time.time()
        
        # Add to buffer
        self.buffer.append(raw_value)
        
        # Filter
        filtered = self._filter_signal(raw_value)
        
        # Update statistics
        self._update_statistics(filtered)
        
        # Normalize
        if self.baseline is None:
            # Auto-initialize from first readings
            if len(self.buffer) >= 30:
                self.calibrate_baseline(list(self.buffer)[:30])
            normalized = 0.0
        else:
            normalized = (filtered - self.baseline) / (self.baseline_std or 1.0)
        
        # Anomaly detection
        anomaly_score = self._calculate_anomaly_score(filtered)
        
        # Require sustained anomaly before trigger (reduce false positives)
        is_anomaly = anomaly_score > self.anomaly_threshold
        if is_anomaly:
            self._anomaly_counter += 1
        else:
            self._anomaly_counter = max(0, self._anomaly_counter - 1)
        
        # Trigger contamination detection
        contaminant_detected = self._anomaly_counter >= self.min_consecutive_anomaly
        
        # ML classification (if available)
        contaminant_type = None
        concentration = None
        
        if self.use_ml and contaminant_detected:
            try:
                features = self._extract_features()
                contaminant_type, concentration = self._ml_inference(features)
            except Exception as e:
                logger.error(f"ML inference failed: {e}")
        
        confidence = 1.0 - min(1.0, anomaly_score / 5.0)
        
        return ProcessedSignal(
            timestamp=timestamp,
            raw_value=raw_value,
            filtered_value=filtered,
            normalized_value=normalized,
            baseline=self.baseline or 0.0,
            anomaly_score=anomaly_score,
            contaminant_detected=contaminant_detected,
            confidence=confidence,
            contaminant_type=contaminant_type,
            concentration_estimate=concentration
        )
    
    def _extract_features(self) -> np.ndarray:
        """Extract features for ML model"""
        if len(self.buffer) < 10:
            return np.zeros(10)
        
        window = list(self.buffer)[-10:]
        features = np.array([
            np.mean(window),
            np.std(window),
            np.max(window) - np.min(window),
            window[-1] - window[0],  # Trend
            np.median(window)
        ])
        
        # Pad to expected size
        if len(features) < 10:
            features = np.pad(features, (0, 10 - len(features)))
        
        return features
    
    def _ml_inference(self, features: np.ndarray) -> Tuple[Optional[str], Optional[float]]:
        """Run ML inference on features"""
        if self.model is None:
            return None, None
        
        # Preprocess
        input_data = features.astype(np.float32).reshape(1, -1)
        
        # Set input tensor
        input_details = self.model.get_input_details()
        output_details = self.model.get_output_details()
        
        self.model.set_tensor(input_details[0]['index'], input_data)
        self.model.invoke()
        
        # Get output
        output = self.model.get_tensor(output_details[0]['index'])
        
        # Decode output (placeholder - depends on model)
        class_idx = np.argmax(output[0])
        confidence = output[0][class_idx]
        
        contaminant_types = ["Heavy Metal", "Pesticide", "Bacteria", "Organic"]
        contaminant = contaminant_types[class_idx % len(contaminant_types)] if confidence > 0.5 else "Unknown"
        
        return contaminant, float(confidence)
    
    def get_trend(self, window_size: int = 60) -> float:
        """Get trend direction (+ increasing, - decreasing, 0 steady)"""
        if len(self.buffer) < window_size:
            return 0.0
        
        recent = list(self.buffer)[-window_size:]
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]
        return slope
    
    def reset(self):
        """Reset processor state"""
        self.buffer.clear()
        self.baseline = None
        self.mean = 0.0
        self.var = 1.0
        self._count = 0
        self._anomaly_counter = 0
        logger.info("Signal processor reset")

if __name__ == "__main__":
    print("Signal processing demo")
    
    processor = SignalProcessor(filter_type="median", anomaly_threshold=2.0)
    
    # Simulate baseline establishment
    print("\nEstablishing baseline...")
    for i in range(30):
        # Normal variation
        value = 100 + np.random.normal(0, 5)
        result = processor.process(value)
        if i % 10 == 0:
            print(f"  Sample {i+1}: raw={value:.1f}, baseline={result.baseline:.1f}")
    
    print(f"\nBaseline established: {processor.baseline:.1f}")
    
    # Simulate contamination event
    print("\nSimulating contamination...")
    for i in range(20):
        if i < 5:
            # Normal
            value = 100 + np.random.normal(0, 5)
        else:
            # Spike (contamination)
            value = 150 + np.random.normal(0, 10)
        
        result = processor.process(value)
        print(f"  {i+1}: raw={value:.1f}, filtered={result.filtered_value:.1f}, "
              f"anomaly={result.anomaly_score:.2f}, detected={result.contaminant_detected}")
