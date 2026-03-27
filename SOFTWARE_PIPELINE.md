# MycoSentinel Software Pipeline
## Real-Time Biosensor Signal Processing & ML Pipeline

**Document Version:** 1.0.0  
**Target:** Raspberry Pi 4 / ESP32-CAM  
**Tech Stack:** Python, TensorFlow Lite, FastAPI, MQTT, InfluxDB

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Optical Signal Processing (Fluorescence)](#optical-signal-processing)
3. [Electrical Signal Processing (Electricigens)](#electrical-signal-processing)
4. [Temporal Analysis](#temporal-analysis)
5. [ML Pipeline](#ml-pipeline)
6. [Real-Time Dashboard](#real-time-dashboard)
7. [Alert System](#alert-system)
8. [Deployment Strategy](#deployment-strategy)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MYCOSENTINEL PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐   ┌─────────────┐         ┌──────────────┐                  │
│  │  Fluorescence│   │ Electricigen │         │   Temperature │                  │
│  │   Sensor    │   │    Sensor    │         │    Sensor     │                  │
│  └──────┬──────┘   └──────┬──────┘         └───────┬──────┘                  │
│         │                  │                        │                       │
│         ▼                  ▼                        ▼                       │
│  ┌─────────────┐   ┌─────────────┐         ┌──────────────┐                  │
│  │  Optical    │   │  Electrical │         │   Temp       │                  │
│  │  Processing │   │  Processing │         │   Processing │                  │
│  └──────┬──────┘   └──────────────┘         └──────────────┘                  │
│         │                                                                     │
│         ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    TEMPORAL ANALYSIS LAYER                        │    │
│  │         (State Tracking, Drift Detection, Validation)             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                     │
│         ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    ML INFERENCE LAYER (TFLite)                      │    │
│  │       (Anomaly Detection, Calibration, Classification)              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                     │
│         ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    STREAMING & DASHBOARD LAYER                      │    │
│  │              (FastAPI, MQTT, WebSocket, InfluxDB)                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                     │
│         ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      ALERT SYSTEM                                   │    │
│  │             (Thresholds, Notifications, Logging)                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Optical Signal Processing

### 2.1 Background Subtraction

Fluorescence readings suffer from ambient light, dark current, and autofluorescence noise.

```python
import numpy as np
from typing import Tuple, List
from dataclasses import dataclass
from collections import deque

@dataclass
class OpticalConfig:
    """Configuration for optical signal processing"""
    led_wavelength: int = 470  # nm (GFP excitation)
    emission_filter: int = 525  # nm (GFP emission)
    integration_time_ms: float = 100.0
    dark_current_samples: int = 10
    rolling_window: int = 5
    
class OpticalProcessor:
    """
    Optical signal processing for fluorescence-based biosensors.
    Handles background subtraction, normalization, and noise reduction.
    """
    
    def __init__(self, config: OpticalConfig):
        self.config = config
        self.dark_current_buffer = deque(maxlen=config.dark_current_samples)
        self.raw_buffer = deque(maxlen=config.rolling_window)
        self.baseline_established = False
        self.baseline_value = 0.0
        
    def capture_dark_frame(self, sensor_interface) -> np.ndarray:
        """
        Capture dark frame with LED OFF to characterize sensor noise.
        Should be called periodically (every N readings or on calibration).
        """
        # Turn off excitation LED
        sensor_interface.set_led_state(False)
        time.sleep(0.01)  # LED decay time
        
        dark_samples = []
        for _ in range(self.config.dark_current_samples):
            dark_samples.append(sensor_interface.read_raw())
            time.sleep(0.005)
            
        dark_frame = np.median(dark_samples, axis=0)
        self.dark_current_buffer.append(dark_frame)
        return dark_frame
    
    def subtract_dark_current(self, raw_signal: float, 
                             dark_estimate: float = None) -> float:
        """Remove dark current from signal"""
        if dark_estimate is None and len(self.dark_current_buffer) > 0:
            dark_estimate = np.mean(self.dark_current_buffer)
        elif dark_estimate is None:
            dark_estimate = 0.0
            
        corrected = raw_signal - dark_estimate
        return max(0.0, corrected)  # No negative fluorescence
    
    def estimate_baseline(self, readings: List[float]) -> float:
        """
        Estimate baseline fluorescence (pre-colonization).
        Uses robust statistics to ignore outliers.
        """
        if len(readings) < 10:
            return np.mean(readings)
            
        # Percentile-based baseline (5th percentile)
        baseline = np.percentile(readings, 5)
        self.baseline_value = baseline
        self.baseline_established = True
        return baseline
    
    def normalize_to_baseline(self, signal: float) -> float:
        """
        Normalize signal to baseline (1.0 = baseline level).
        Tracks fold-change above background.
        """
        if not self.baseline_established or self.baseline_value == 0:
            return signal
            
        normalized = signal / self.baseline_value
        return normalized
    
    def temperature_compensation(self, signal: float, 
                                  temp_celsius: float,
                                  temp_coefficient: float = -0.01) -> float:
        """
        Compensate for GFP quantum yield temperature dependence.
        GFP fluorescence decreases ~1% per °C above 25°C.
        """
        reference_temp = 25.0
        temp_delta = temp_celsius - reference_temp
        correction_factor = 1.0 - (temp_delta * temp_coefficient)
        return signal / correction_factor
    
    def process(self, raw_signal: float, 
                temperature: float,
                dark_frame: float = None) -> dict:
        """
        Full optical processing pipeline.
        
        Returns:
            dict with raw, corrected, normalized values and quality metrics
        """
        # Step 1: Dark current subtraction
        corrected = self.subtract_dark_current(raw_signal, dark_frame)
        
        # Step 2: Temperature compensation
        temp_corrected = self.temperature_compensation(corrected, temperature)
        
        # Step 3: Rolling average for noise reduction
        self.raw_buffer.append(temp_corrected)
        smoothed = np.mean(self.raw_buffer)
        
        # Step 4: Normalize to baseline
        normalized = self.normalize_to_baseline(smoothed)
        
        # Quality metrics
        snr = self._calculate_snr(temp_corrected)
        
        return {
            'timestamp': time.time(),
            'raw': raw_signal,
            'dark_corrected': corrected,
            'temp_corrected': temp_corrected,
            'smoothed': smoothed,
            'normalized': normalized,
            'fold_change': normalized,
            'signal_to_noise': snr,
            'quality': 'good' if snr > 10 else 'poor'
        }
    
    def _calculate_snr(self, signal: float, noise_estimate: float = None) -> float:
        """Calculate signal-to-noise ratio"""
        if noise_estimate is None and len(self.dark_current_buffer) > 0:
            noise_estimate = np.std(self.dark_current_buffer)
        if noise_estimate is None or noise_estimate == 0:
            return float('inf')
        return signal / noise_estimate
```

### 2.2 Calibration Curve Management

```python
class FluorescenceCalibrator:
    """
    Manages calibration curves for converting fluorescence to analyte concentration.
    Supports linear, polynomial, and sigmoid (Hill) models.
    """
    
    def __init__(self):
        self.calibration_points = []  # (concentration, fluorescence)
        self.model_type = 'hill'  # 'linear', 'polynomial', 'hill'
        self.model_params = None
        self.r_squared = 0.0
        
    def add_calibration_point(self, concentration: float, fluorescence: float):
        """Add a calibration measurement"""
        self.calibration_points.append((concentration, fluorescence))
        
    def fit_model(self) -> bool:
        """Fit calibration model to points"""
        if len(self.calibration_points) < 3:
            return False
            
        concentrations = np.array([p[0] for p in self.calibration_points])
        fluorescence = np.array([p[1] for p in self.calibration_points])
        
        if self.model_type == 'hill':
            # Hill equation: F = F_min + (F_max - F_min) / (1 + (K/conc)^n)
            from scipy.optimize import curve_fit
            
            def hill_eq(x, f_min, f_max, k_d, n):
                return f_min + (f_max - f_min) / (1 + np.power(k_d / np.maximum(x, 1e-10), n))
            
            try:
                popt, _ = curve_fit(hill_eq, concentrations, fluorescence, 
                                   p0=[min(fluorescence), max(fluorescence), 
                                       np.median(concentrations), 1.0])
                self.model_params = popt
                
                # Calculate R²
                predicted = hill_eq(concentrations, *popt)
                ss_res = np.sum((fluorescence - predicted) ** 2)
                ss_tot = np.sum((fluorescence - np.mean(fluorescence)) ** 2)
                self.r_squared = 1 - (ss_res / ss_tot)
                
                return True
            except:
                return False
                
        return False
    
    def fluorescence_to_concentration(self, fluorescence: float) -> tuple:
        """
        Convert fluorescence reading to analyte concentration.
        Returns (concentration, confidence).
        """
        if self.model_params is None:
            return (None, 0.0)
            
        # Inverse Hill equation (approximate)
        f_min, f_max, k_d, n = self.model_params
        
        if fluorescence <= f_min:
            return (0.0, 0.1)
        if fluorescence >= f_max * 0.99:
            return (float('inf'), 0.0)  # Saturated
            
        # Solve for concentration
        ratio = (f_max - f_min) / (fluorescence - f_min) - 1
        if ratio <= 0:
            return (float('inf'), 0.0)
            
        concentration = k_d * np.power(ratio, 1.0 / n)
        confidence = self.r_squared * (0.8 if fluorescence < f_max * 0.9 else 0.5)
        
        return (concentration, confidence)
```

---

## Electrical Signal Processing

### 3.1 Impedance & Current Measurement

```python
import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq

@dataclass
class ElectricalConfig:
    """Configuration for electrical biosensor processing"""
    sampling_rate_hz: float = 100.0  # For chronoamperometry
    adc_resolution: int = 16
    v_ref: float = 3.3
    r_feedback: float = 10000.0  # Ohms (transimpedance amp)
    filter_cutoff_hz: float = 10.0
    noise_window_size: int = 50

class ElectricalProcessor:
    """
    Signal processing for electricigen-based biosensors.
    Handles current measurement, impedance analysis, and noise filtering.
    """
    
    def __init__(self, config: ElectricalConfig):
        self.config = config
        self.raw_buffer = deque(maxlen=config.noise_window_size)
        self.baseline_current = 0.0
        self.is_baseline_set = False
        
        # Design filter
        nyquist = config.sampling_rate_hz / 2
        normalized_cutoff = config.filter_cutoff_hz / nyquist
        self.b, self.a = signal.butter(4, normalized_cutoff, btype='low')
        self.zi = signal.lfilter_zi(self.b, self.a)
        
    def adc_to_voltage(self, adc_value: int) -> float:
        """Convert ADC reading to voltage"""
        max_adc = (1 << self.config.adc_resolution) - 1
        return (adc_value / max_adc) * self.config.v_ref
    
    def voltage_to_current(self, voltage: float) -> float:
        """
        Convert measured voltage to current (for transimpedance amplifier).
        V_out = I * R_feedback
        """
        return voltage / self.config.r_feedback
    
    def measure_noise_spectrum(self, raw_readings: np.ndarray) -> dict:
        """
        Analyze noise frequency spectrum to identify interference sources.
        Returns dominant frequency components.
        """
        # Detrend
        detrended = signal.detrend(raw_readings)
        
        # FFT
        fft_vals = np.abs(rfft(detrended))
        freqs = rfftfreq(len(raw_readings), 1.0 / self.config.sampling_rate_hz)
        
        # Find peaks
        from scipy.signal import find_peaks
        peaks, properties = find_peaks(fft_vals, height=np.mean(fft_vals) * 2)
        
        noise_profile = {
            'dominant_freqs': freqs[peaks].tolist() if len(peaks) > 0 else [],
            'peak_magnitudes': fft_vals[peaks].tolist() if len(peaks) > 0 else [],
            'total_noise_power': np.sum(fft_vals ** 2),
            'suggest_60hz': any(55 < f < 65 for f in freqs[peaks]) if len(peaks) > 0 else False
        }
        
        return noise_profile
    
    def adaptive_filter(self, measurement: float, 
                       noise_estimate: float = None) -> float:
        """
        Adaptive noise filtering based on real-time noise characterization.
        Uses combination of IIR filter and median filter for spike rejection.
        """
        self.raw_buffer.append(measurement)
        
        if len(self.raw_buffer) < 3:
            return measurement
            
        # Median filter for spike rejection
        median_val = np.median(self.raw_buffer)
        
        # IIR lowpass for smoothing
        filtered, self.zi = signal.lfilter(self.b, self.a, [measurement], zi=self.zi)
        
        # Adaptive weight based on deviation from median
        deviation = abs(measurement - median_val)
        if noise_estimate:
            adaptivity = min(1.0, deviation / (3 * noise_estimate))
        else:
            adaptivity = 0.5
            
        # Blend median and IIR
        result = adaptivity * median_val + (1 - adaptivity) * filtered[0]
        return result
    
    def detect_electrode_drift(self, current_readings: List[float], 
                               window_size: int = 100) -> dict:
        """
        Detect electrode drift/fouling by analyzing baseline trends.
        Drift indicates electrode degradation or biofilm formation.
        """
        if len(current_readings) < window_size:
            return {'drift_detected': False, 'drift_rate': 0.0}
            
        # Linear regression on recent window
        x = np.arange(window_size)
        y = np.array(current_readings[-window_size:])
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # Drift metrics
        relative_drift = abs(slope) / np.mean(y) if np.mean(y) != 0 else 0
        drift_detected = relative_drift > 0.01  # 1% per reading threshold
        
        return {
            'drift_detected': drift_detected,
            'drift_rate': slope,
            'relative_drift': relative_drift,
            'p_value': p_value,
            'r_squared': r_value ** 2,
            'trend': 'increasing' if slope > 0 else 'decreasing'
        }
    
    def process(self, adc_raw: int, temperature: float = 25.0) -> dict:
        """
        Full electrical signal processing pipeline.
        """
        # Convert ADC to voltage
        voltage = self.adc_to_voltage(adc_raw)
        
        # Convert to current
        current = self.voltage_to_current(voltage)
        
        # Temperature compensation (electrolyte conductivity)
        # Conductivity increases ~2% per °C
        temp_compensation = 1.0 + (temperature - 25.0) * 0.02
        current_compensated = current / temp_compensation
        
        # Adaptive filtering
        noise_estimate = np.std(self.raw_buffer) if len(self.raw_buffer) > 10 else None
        filtered = self.adaptive_filter(current_compensated, noise_estimate)
        
        # Baseline subtraction if established
        if self.is_baseline_set:
            delta_current = filtered - self.baseline_current
            normalized = delta_current / abs(self.baseline_current) if self.baseline_current != 0 else 0
        else:
            delta_current = filtered
            normalized = 0.0
            
        return {
            'timestamp': time.time(),
            'adc_raw': adc_raw,
            'voltage_v': voltage,
            'current_a': current,
            'current_compensated_a': current_compensated,
            'current_filtered_a': filtered,
            'delta_current_a': delta_current,
            'normalized_response': normalized,
            'temperature_c': temperature
        }
    
    def set_baseline(self, baseline_readings: List[float]):
        """Establish baseline current"""
        self.baseline_current = np.median(baseline_readings)
        self.is_baseline_set = True
```

---

## Temporal Analysis

### 4.1 State Machine for Signal Validation

```python
from enum import Enum, auto
from typing import Optional
from collections import deque
import numpy as np

class SignalState(Enum):
    """States for signal validation state machine"""
    INITIALIZING = auto()      # Waiting for stable baseline
    BASELINE = auto()          # Stable baseline established
    TRANSIENT = auto()         # Signal changing rapidly
    RESPONSE = auto()          # Confirmed analyte response
    DECAY = auto()             # Signal returning to baseline
    SATURATION = auto()        # Signal at maximum (saturated)
    ANOMALY = auto()           # Unusual pattern detected
    CONTAMINATION = auto()     # Suspected contamination

class TemporalAnalyzer:
    """
    Temporal analysis engine for distinguishing real signals from noise.
    Tracks signal evolution over time and validates against expected patterns.
    """
    
    def __init__(self, 
                 response_time_s: float = 60.0,  # Expected response time
                 stabilization_time_s: float = 300.0,
                 sampling_interval_s: float = 1.0):
        
        self.response_time_s = response_time_s
        self.stabilization_time_s = stabilization_time_s
        self.sampling_interval_s = sampling_interval_s
        
        # Buffers
        self.time_buffer = deque(maxlen=int(600 / sampling_interval_s))  # 10 min history
        self.value_buffer = deque(maxlen=int(600 / sampling_interval_s))
        self.state = SignalState.INITIALIZING
        
        # Tracking
        self.baseline_mean = 0.0
        self.baseline_std = 0.0
        self.response_start_time = None
        self.peak_value = 0.0
        self.peak_time = None
        
        # Parameters (tunable)
        self.response_threshold_sigma = 3.0  # Sigma for response detection
        self.transient_min_duration = 10  # samples
        self.contamination_threshold = 5.0  # Multiplier above baseline
        
    def update(self, timestamp: float, value: float) -> dict:
        """
        Process new reading and update state machine.
        
        Returns:
            dict with state, confidence, and derived metrics
        """
        self.time_buffer.append(timestamp)
        self.value_buffer.append(value)
        
        # Calculate rolling statistics
        if len(self.value_buffer) >= 10:
            self.baseline_mean = np.mean(list(self.value_buffer)[-50:])
            self.baseline_std = np.std(list(self.value_buffer)[-50:])
            
        # State transitions
        old_state = self.state
        self._update_state(timestamp, value)
        
        # Calculate metrics
        metrics = self._calculate_metrics(timestamp, value)
        
        return {
            'state': self.state.name,
            'previous_state': old_state.name if old_state != self.state else None,
            'baseline_mean': self.baseline_mean,
            'baseline_std': self.baseline_std,
            'z_score': (value - self.baseline_mean) / self.baseline_std if self.baseline_std > 0 else 0,
            'confidence': self._calculate_confidence(),
            'is_valid_response': self.state == SignalState.RESPONSE,
            **metrics
        }
    
    def _update_state(self, timestamp: float, value: float):
        """Update state machine based on current readings"""
        
        if len(self.value_buffer) < 20:
            self.state = SignalState.INITIALIZING
            return
            
        z_score = (value - self.baseline_mean) / self.baseline_std if self.baseline_std > 0 else 0
        
        # Calculate trend
        if len(self.value_buffer) >= 10:
            recent = list(self.value_buffer)[-10:]
            trend = (recent[-1] - recent[0]) / len(recent)
        else:
            trend = 0
            
        # State logic
        if abs(z_score) > self.contamination_threshold:
            self.state = SignalState.CONTAMINATION
            return
            
        if self.state == SignalState.INITIALIZING:
            if len(self.value_buffer) >= 50 and self._is_stable():
                self.state = SignalState.BASELINE
                
        elif self.state == SignalState.BASELINE:
            if z_score > self.response_threshold_sigma:
                self.state = SignalState.TRANSIENT
                self.response_start_time = timestamp
            elif abs(trend) > self.baseline_std * 0.1:
                self.state = SignalState.ANOMALY
                
        elif self.state == SignalState.TRANSIENT:
            duration = timestamp - self.response_start_time if self.response_start_time else 0
            
            if z_score > self.response_threshold_sigma and duration > self.response_time_s:
                self.state = SignalState.RESPONSE
            elif z_score < self.response_threshold_sigma * 0.5:
                self.state = SignalState.ANOMALY if duration < self.response_time_s else SignalState.DECAY
                
        elif self.state == SignalState.RESPONSE:
            if z_score < self.response_threshold_sigma * 0.5:
                self.state = SignalState.DECAY
            elif self._is_saturated(value):
                self.state = SignalState.SATURATION
                
        elif self.state == SignalState.DECAY:
            if self._is_stable():
                self.state = SignalState.BASELINE
                self.response_start_time = None
            elif z_score > self.response_threshold_sigma:
                self.state = SignalState.TRANSIENT
                
        elif self.state in [SignalState.SATURATION, SignalState.ANOMALY, SignalState.CONTAMINATION]:
            if self._is_stable() and abs(z_score) < self.response_threshold_sigma:
                self.state = SignalState.BASELINE
    
    def _is_stable(self, window: int = 30) -> bool:
        """Check if signal is stable"""
        if len(self.value_buffer) < window:
            return False
        recent = list(self.value_buffer)[-window:]
        return np.std(recent) / np.mean(recent) < 0.05 if np.mean(recent) > 0 else False
    
    def _is_saturated(self, value: float) -> bool:
        """Check if reading appears saturated"""
        if len(self.value_buffer) < 10:
            return False
        recent = list(self.value_buffer)[-10:]
        return value > max(recent) * 0.95 and value > self.baseline_mean * 10
    
    def _calculate_metrics(self, timestamp: float, value: float) -> dict:
        """Calculate temporal metrics"""
        metrics = {
            'time_since_response_start': None,
            'response_rate': 0.0,
            'estimated_recovery_time': None,
            'slope_instantaneous': 0.0
        }
        
        if self.response_start_time:
            metrics['time_since_response_start'] = timestamp - self.response_start_time
            
        if len(self.value_buffer) >= 5:
            recent = list(self.value_buffer)[-5:]
            metrics['slope_instantaneous'] = (recent[-1] - recent[0]) / 5
            
            if self.state == SignalState.RESPONSE:
                metrics['response_rate'] = (value - self.baseline_mean) / self.baseline_mean if self.baseline_mean > 0 else 0
                
        return metrics
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence in current state"""
        if self.state == SignalState.INITIALIZING:
            return 0.0
        elif self.state == SignalState.CONTAMINATION:
            return 0.1
        elif self.state in [SignalState.ANOMALY, SignalState.SATURATION]:
            return 0.5
        elif self.state == SignalState.BASELINE:
            return min(1.0, len(self.value_buffer) / 100)
        else:
            return 0.8
```

### 4.2 Drift Detection

```python
class DriftDetector:
    """Detects long-term sensor drift and contamination"""
    
    def __init__(self, window_hours: float = 24.0, 
                 drift_threshold: float = 0.1):  # 10% drift
        self.window_hours = window_hours
        self.drift_threshold = drift_threshold
        self.hourly_averages = deque(maxlen=int(window_hours))
        
    def update_hourly(self, avg_value: float):
        """Add hourly average reading"""
        self.hourly_averages.append({
            'hour': len(self.hourly_averages),
            'value': avg_value
        })
        
    def detect_drift(self) -> dict:
        """Detect drift in recent readings"""
        if len(self.hourly_averages) < 6:  # Need 6 hours of data
            return {'drift_detected': False, 'drift_percent': 0.0}
            
        values = [h['value'] for h in self.hourly_averages]
        
        # Linear regression for trend
        x = np.arange(len(values))
        slope, intercept, r_value, _, _ = stats.linregress(x, values)
        
        # Calculate drift as percentage of mean
        mean_val = np.mean(values)
        drift_per_hour = slope / mean_val if mean_val > 0 else 0
        total_drift = drift_per_hour * len(values)
        
        return {
            'drift_detected': abs(total_drift) > self.drift_threshold,
            'drift_percent': total_drift * 100,
            'drift_per_hour': drift_per_hour * 100,
            'trend': 'increasing' if slope > 0 else 'decreasing',
            'r_squared': r_value ** 2,
            'recommendation': 'calibration_needed' if abs(total_drift) > self.drift_threshold else 'none'
        }
```

---

## ML Pipeline

### 5.1 Anomaly Detection Model (Autoencoder)

```python
import tensorflow as tf
import numpy as np
from pathlib import Path

class BiosensorAnomalyDetector:
    """
    LSTM-based autoencoder for anomaly detection in biosensor time series.
    Optimized for TensorFlow Lite deployment on edge devices.
    """
    
    def __init__(self, sequence_length: int = 60, n_features: int = 4):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.model = None
        self.threshold = None
        self.is_trained = False
        
    def build_model(self, latent_dim: int = 8) -> tf.keras.Model:
        """
        Build LSTM autoencoder for anomaly detection.
        Small enough for TFLite conversion.
        """
        # Encoder
        inputs = tf.keras.Input(shape=(self.sequence_length, self.n_features))
        
        # LSTM encoder
        x = tf.keras.layers.LSTM(32, activation='tanh', return_sequences=True)(inputs)
        x = tf.keras.layers.Dropout(0.2)(x)
        x = tf.keras.layers.LSTM(16, activation='tanh', return_sequences=False)(x)
        encoded = tf.keras.layers.Dense(latent_dim, activation='relu')(x)
        
        # Decoder (repeat vector to get back to sequence)
        x = tf.keras.layers.RepeatVector(self.sequence_length)(encoded)
        x = tf.keras.layers.LSTM(16, activation='tanh', return_sequences=True)(x)
        x = tf.keras.layers.LSTM(32, activation='tanh', return_sequences=True)(x)
        decoded = tf.keras.layers.TimeDistributed(
            tf.keras.layers.Dense(self.n_features)
        )(x)
        
        autoencoder = tf.keras.Model(inputs, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')
        
        self.model = autoencoder
        return autoencoder
    
    def prepare_sequence(self, readings: list) -> np.ndarray:
        """
        Prepare sequence for model input.
        Features: [normalized_value, temp, rate_of_change, time_of_day]
        """
        if len(readings) < self.sequence_length:
            # Pad with copies of first reading
            padding = [readings[0]] * (self.sequence_length - len(readings))
            readings = padding + readings
            
        # Extract features
        sequences = []
        for i in range(len(readings) - self.sequence_length + 1):
            window = readings[i:i + self.sequence_length]
            
            feature_matrix = np.zeros((self.sequence_length, self.n_features))
            for j, reading in enumerate(window):
                feature_matrix[j, 0] = reading.get('normalized', 0)
                feature_matrix[j, 1] = reading.get('temperature', 25.0) / 50.0  # Normalized
                
                # Rate of change
                if j > 0:
                    feature_matrix[j, 2] = (window[j]['normalized'] - window[j-1]['normalized']) if j > 0 else 0
                else:
                    feature_matrix[j, 2] = 0
                    
                # Time of day (cyclical encoding)
                ts = reading.get('timestamp', 0)
                hour = (ts % 86400) / 86400
                feature_matrix[j, 3] = np.sin(hour * 2 * np.pi)
                
            sequences.append(feature_matrix)
            
        return np.array(sequences)
    
    def train(self, normal_data: list, epochs: int = 50, validation_split: float = 0.1):
        """Train autoencoder on normal (non-anomalous) data"""
        sequences = self.prepare_sequence(normal_data)
        
        # Train
        history = self.model.fit(
            sequences, sequences,
            epochs=epochs,
            batch_size=32,
            validation_split=validation_split,
            verbose=1
        )
        
        # Calculate reconstruction error threshold (95th percentile)
        reconstructions = self.model.predict(sequences)
        mse = np.mean(np.power(sequences - reconstructions, 2), axis=(1, 2))
        self.threshold = np.percentile(mse, 95)
        self.is_trained = True
        
        return history
    
    def detect(self, recent_readings: list) -> dict:
        """
        Detect anomalies in recent readings.
        Returns anomaly score and classification.
        """
        if not self.is_trained or self.model is None:
            return {'anomaly': False, 'score': 0.0, 'confidence': 0.0}
            
        sequences = self.prepare_sequence(recent_readings)
        if len(sequences) == 0:
            return {'anomaly': False, 'score': 0.0, 'confidence': 0.0}
            
        reconstructions = self.model.predict(sequences[-1:])
        mse = np.mean(np.power(sequences[-1:] - reconstructions, 2))
        
        return {
            'anomaly': mse > self.threshold,
            'score': float(mse),
            'threshold': float(self.threshold),
            'confidence': min(1.0, mse / (self.threshold * 2)) if self.threshold > 0 else 0.0,
            'severity': 'high' if mse > self.threshold * 2 else 'medium' if mse > self.threshold else 'low'
        }
    
    def convert_to_tflite(self, output_path: str) -> str:
        """Convert model to TensorFlow Lite for edge deployment"""
        converter = tf.lite.TFLiteConverter.from_keras_model(self.model)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.target_spec.supported_types = [tf.float16]
        
        tflite_model = converter.convert()
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(tflite_model)
            
        return output_path


class TFLiteInferenceEngine:
    """Lightweight TFLite inference for Raspberry Pi/ESP32"""
    
    def __init__(self, model_path: str):
        self.interpreter = tf.lite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        self.input_index = self.interpreter.get_input_details()[0]['index']
        self.output_index = self.interpreter.get_output_details()[0]['index']
        
    def predict(self, sequence: np.ndarray) -> np.ndarray:
        """Run inference on single sequence"""
        self.interpreter.set_tensor(self.input_index, sequence.astype(np.float32))
        self.interpreter.invoke()
        return self.interpreter.get_tensor(self.output_index)
```

### 5.2 Calibration Transfer Learning

```python
class OnlineCalibrator:
    """
    Online calibration using transfer learning.
    Adapts to sensor drift without full retraining.
    """
    
    def __init__(self, base_model_path: str):
        self.base_model = tf.keras.models.load_model(base_model_path)
        self.calibration_data = []
        self.drift_offset = 0.0
        self.drift_scale = 1.0
        
    def add_calibration_sample(self, sensor_value: float, reference_value: float):
        """Add ground truth calibration point"""
        self.calibration_data.append({
            'sensor': sensor_value,
            'reference': reference_value
        })
        
        # Recalculate drift if we have enough points
        if len(self.calibration_data) >= 3:
            self._update_calibration()
    
    def _update_calibration(self):
        """Update calibration parameters using linear regression"""
        if len(self.calibration_data) < 2:
            return
            
        x = np.array([d['sensor'] for d in self.calibration_data])
        y = np.array([d['reference'] for d in self.calibration_data])
        
        # Linear fit: y = a * x + b
        A = np.vstack([x, np.ones(len(x))]).T
        self.drift_scale, self.drift_offset = np.linalg.lstsq(A, y, rcond=None)[0]
    
    def calibrate(self, sensor_value: float) -> float:
        """Apply calibration correction"""
        return self.drift_scale * sensor_value + self.drift_offset
```

---

## Real-Time Dashboard

### 6.1 FastAPI Backend

```python
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from datetime import datetime
from typing import Dict, List
import paho.mqtt.client as mqtt
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

app = FastAPI(title="MycoSentinel Dashboard", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SensorDashboard:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.sensor_data: Dict[str, dict] = {}
        self.alerts: List[dict] = []
        
        # InfluxDB setup
        self.influx_client = influxdb_client.InfluxDBClient(
            url="http://localhost:8086",
            token="your-token",
            org="mycosentinel"
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.influx_client.query_api()
        
        # MQTT setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self._on_mqtt_message
        
    async def start_mqtt(self):
        """Start MQTT client"""
        self.mqtt_client.connect("localhost", 1883, 60)
        self.mqtt_client.subscribe("mycosentinel/sensors/+")
        self.mqtt_client.loop_start()
        
    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT sensor data"""
        try:
            payload = json.loads(msg.payload.decode())
            sensor_id = msg.topic.split('/')[-1]
            
            # Store in memory
            self.sensor_data[sensor_id] = {
                **payload,
                'last_update': datetime.now().isoformat()
            }
            
            # Write to InfluxDB
            point = influxdb_client.Point("sensor_reading") \
                .tag("sensor_id", sensor_id) \
                .field("value", payload.get('value', 0)) \
                .field("temperature", payload.get('temperature', 0)) \
                .field("confidence", payload.get('confidence', 0)) \
                .time(datetime.utcnow())
            
            self.write_api.write(bucket="biosensor_data", record=point)
            
            # Broadcast to WebSocket clients
            asyncio.create_task(self._broadcast({
                'type': 'sensor_update',
                'sensor_id': sensor_id,
                'data': payload
            }))
            
        except Exception as e:
            print(f"Error processing MQTT message: {e}")
    
    async def _broadcast(self, message: dict):
        """Broadcast to all connected WebSocket clients"""
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except:
                disconnected.append(conn)
        
        for conn in disconnected:
            self.active_connections.remove(conn)

dashboard = SensorDashboard()

@app.on_event("startup")
async def startup():
    await dashboard.start_mqtt()

@app.get("/")
async def root():
    return {"status": "MycoSentinel Dashboard API", "version": "1.0.0"}

@app.get("/api/sensors")
async def get_sensors():
    """Get list of all sensors and their status"""
    return {
        "sensors": [
            {
                "id": sensor_id,
                "status": "active" if data.get('value') is not None else "offline",
                "last_update": data.get('last_update'),
                "current_value": data.get('value'),
                "temperature": data.get('temperature'),
                "confidence": data.get('confidence')
            }
            for sensor_id, data in dashboard.sensor_data.items()
        ]
    }

@app.get("/api/sensors/{sensor_id}/history")
async def get_sensor_history(sensor_id: str, hours: int = 24):
    """Get historical data for a sensor from InfluxDB"""
    query = f'''
    from(bucket: "biosensor_data")
        |> range(start: -{hours}h)
        |> filter(fn: (r) => r._measurement == "sensor_reading")
        |> filter(fn: (r) => r.sensor_id == "{sensor_id}")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    
    try:
        result = dashboard.query_api.query_data_frame(query)
        if result.empty:
            return {"sensor_id": sensor_id, "data": []}
            
        data = []
        for _, row in result.iterrows():
            data.append({
                "timestamp": row['_time'].isoformat(),
                "value": row.get('value'),
                "temperature": row.get('temperature'),
                "confidence": row.get('confidence')
            })
            
        return {"sensor_id": sensor_id, "data": data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    dashboard.active_connections.append(websocket)
    
    try:
        while True:
            # Wait for client messages (ping, etc.)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get('action') == 'ping':
                await websocket.send_json({'type': 'pong'})
            elif message.get('action') == 'get_sensors':
                await websocket.send_json({
                    'type': 'sensor_list',
                    'data': list(dashboard.sensor_data.keys())
                })
                
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if websocket in dashboard.active_connections:
            dashboard.active_connections.remove(websocket)
```

### 6.2 HTML Dashboard (Served by FastAPI)

```python
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MycoSentinel Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(90deg, #1e293b, #0f172a);
            padding: 20px;
            border-bottom: 1px solid #334155;
        }
        .header h1 {
            font-size: 24px;
            background: linear-gradient(90deg, #22c55e, #10b981);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .sensor-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .sensor-card {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #334155;
            transition: all 0.3s ease;
        }
        .sensor-card:hover {
            border-color: #22c55e;
            box-shadow: 0 0 20px rgba(34, 197, 94, 0.1);
        }
        .sensor-card.alert {
            border-color: #ef4444;
            background: linear-gradient(135deg, #1e293b, #450a0a);
        }
        .sensor-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .sensor-id {
            font-weight: 600;
            font-size: 16px;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-badge.active {
            background: #22c55e;
            color: #000;
        }
        .status-badge.warning {
            background: #f59e0b;
            color: #000;
        }
        .status-badge.alert {
            background: #ef4444;
            color: #fff;
        }
        .metric-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .metric {
            text-align: center;
            padding: 10px;
            background: #0f172a;
            border-radius: 8px;
        }
        .metric-value {
            font-size: 20px;
            font-weight: 700;
            color: #22c55e;
        }
        .metric-value.alert {
            color: #ef4444;
        }
        .metric-label {
            font-size: 11px;
            color: #64748b;
            margin-top: 4px;
        }
        .chart-container {
            height: 150px;
            position: relative;
        }
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .connection-status.connected {
            background: #22c55e;
            color: #000;
        }
        .connection-status.disconnected {
            background: #ef4444;
            color: #fff;
        }
        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: currentColor;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .alert-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            max-width: 400px;
        }
        .alert-item {
            background: #450a0a;
            border: 1px solid #ef4444;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .alert-title {
            font-weight: 600;
            color: #ef4444;
            margin-bottom: 5px;
        }
        .alert-message {
            font-size: 13px;
            color: #fca5a5;
        }
        .alert-time {
            font-size: 11px;
            color: #7f1d1d;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🍄 MycoSentinel Dashboard</h1>
        <p style="color: #64748b; margin-top: 5px;">Real-time Biosensor Monitoring</p>
    </div>
    
    <div class="connection-status disconnected" id="connStatus">
        <span class="dot"></span>
        <span id="connText">Disconnected</span>
    </div>
    
    <div class="container">
        <div class="sensor-grid" id="sensorGrid"></div>
    </div>
    
    <div class="alert-panel" id="alertPanel"></div>
    
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        const sensorData = new Map();
        const charts = new Map();
        
        ws.onopen = () => {
            document.getElementById('connStatus').className = 'connection-status connected';
            document.getElementById('connText').textContent = 'Connected';
            ws.send(JSON.stringify({action: 'get_sensors'}));
        };
        
        ws.onclose = () => {
            document.getElementById('connStatus').className = 'connection-status disconnected';
            document.getElementById('connText').textContent = 'Disconnected';
        };
        
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        };
        
        function handleMessage(msg) {
            if (msg.type === 'sensor_update') {
                updateSensorCard(msg.sensor_id, msg.data);
            } else if (msg.type === 'alert') {
                showAlert(msg);
            }
        }
        
        function updateSensorCard(sensorId, data) {
            if (!sensorData.has(sensorId)) {
                createSensorCard(sensorId);
            }
            
            sensorData.set(sensorId, data);
            const card = document.getElementById(`card-${sensorId}`);
            
            // Update metrics
            const valueEl = card.querySelector('.metric-value.value');
            valueEl.textContent = (data.value || 0).toFixed(3);
            valueEl.className = `metric-value value ${data.anomaly ? 'alert' : ''}`;
            
            card.querySelector('.metric-value.temp').textContent = 
                `${(data.temperature || 0).toFixed(1)}°C`;
            card.querySelector('.metric-value.confidence').textContent = 
                `${((data.confidence || 0) * 100).toFixed(0)}%`;
            
            // Update chart
            updateChart(sensorId, data);
            
            // Update status badge
            const badge = card.querySelector('.status-badge');
            if (data.anomaly) {
                badge.className = 'status-badge alert';
                badge.textContent = 'ANOMALY';
                card.classList.add('alert');
            } else if (data.confidence < 0.5) {
                badge.className = 'status-badge warning';
                badge.textContent = 'LOW CONF';
            } else {
                badge.className = 'status-badge active';
                badge.textContent = 'ACTIVE';
                card.classList.remove('alert');
            }
        }
        
        function createSensorCard(sensorId) {
            const grid = document.getElementById('sensorGrid');
            const card = document.createElement('div');
            card.className = 'sensor-card';
            card.id = `card-${sensorId}`;
            
            card.innerHTML = `
                <div class="sensor-header">
                    <span class="sensor-id">${sensorId}</span>
                    <span class="status-badge active">ACTIVE</span>
                </div>
                <div class="metric-row">
                    <div class="metric">
                        <div class="metric-value value">--</div>
                        <div class="metric-label">Value</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value temp">--</div>
                        <div class="metric-label">Temp</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value confidence">--</div>
                        <div class="metric-label">Confidence</div>
                    </div>
                </div>
                <div class="chart-container">
                    <canvas id="chart-${sensorId}"></canvas>
                </div>
            `;
            
            grid.appendChild(card);
            initChart(sensorId);
        }
        
        function initChart(sensorId) {
            const ctx = document.getElementById(`chart-${sensorId}`).getContext('2d');
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Value',
                        data: [],
                        borderColor: '#22c55e',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { display: false },
                        y: {
                            display: true,
                            grid: { color: '#334155' },
                            ticks: { color: '#64748b', font: { size: 10 } }
                        }
                    },
                    animation: { duration: 0 }
                }
            });
            charts.set(sensorId, chart);
        }
        
        function updateChart(sensorId, data) {
            const chart = charts.get(sensorId);
            if (!chart) return;
            
            const now = new Date().toLocaleTimeString();
            
            chart.data.labels.push(now);
            chart.data.datasets[0].data.push(data.value || 0);
            
            // Keep last 50 points
            if (chart.data.labels.length > 50) {
                chart.data.labels.shift();
                chart.data.datasets[0].data.shift();
            }
            
            // Color based on anomaly
            if (data.anomaly) {
                chart.data.datasets[0].borderColor = '#ef4444';
                chart.data.datasets[0].backgroundColor = 'rgba(239, 68, 68, 0.1)';
            } else {
                chart.data.datasets[0].borderColor = '#22c55e';
                chart.data.datasets[0].backgroundColor = 'rgba(34, 197, 94, 0.1)';
            }
            
            chart.update('none');
        }
        
        function showAlert(alert) {
            const panel = document.getElementById('alertPanel');
            const item = document.createElement('div');
            item.className = 'alert-item';
            item.innerHTML = `
                <div class="alert-title">${alert.title}</div>
                <div class="alert-message">${alert.message}</div>
                <div class="alert-time">${new Date().toLocaleString()}</div>
            `;
            panel.appendChild(item);
            
            setTimeout(() => item.remove(), 30000);
        }
        
        // Ping every 30s to keep connection alive
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({action: 'ping'}));
            }
        }, 30000);
    </script>
</body>
</html>
"""

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    """Serve the dashboard HTML"""
    return HTMLResponse(content=DASHBOARD_HTML)
```

---

## Alert System

### 7.1 Threshold Logic & Notifications

```python
from enum import Enum, auto
from dataclasses import dataclass
from typing import Callable, List, Optional
import asyncio
import smtplib
from email.mime.text import MIMEText

class AlertLevel(Enum):
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()
    EMERGENCY = auto()

@dataclass
class AlertThreshold:
    """Configurable threshold for alerts"""
    sensor_id: str
    metric: str  # 'value', 'temperature', 'anomaly_score', etc.
    comparison: str  # 'gt', 'lt', 'eq', 'range'
    threshold_value: float
    threshold_max: Optional[float] = None  # For range comparisons
    duration_seconds: float = 0.0  # Time condition must persist
    level: AlertLevel = AlertLevel.WARNING
    message_template: str = ""
    cooldown_seconds: float = 300.0  # 5 min default cooldown

class AlertManager:
    """
    Intelligent alert system with hysteresis, cooldowns, and multi-channel notifications.
    """
    
    def __init__(self):
        self.thresholds: List[AlertThreshold] = []
        self.alert_history: deque = deque(maxlen=1000)
        self.active_alerts: dict = {}  # sensor_metric -> last_alert_time
        self.condition_start: dict = {}  # sensor_metric -> timestamp when condition started
        self.handlers: List[Callable] = []
        
        # Default thresholds
        self._add_default_thresholds()
    
    def _add_default_thresholds(self):
        """Add sensible default thresholds"""
        defaults = [
            # Anomaly detection
            AlertThreshold(
                sensor_id='*',  # All sensors
                metric='anomaly_score',
                comparison='gt',
                threshold_value=0.8,
                duration_seconds=30,
                level=AlertLevel.CRITICAL,
                message_template="🚨 ANOMALY DETECTED on {sensor_id}: Score {value:.2f}"
            ),
            
            # Low confidence
            AlertThreshold(
                sensor_id='*',
                metric='confidence',
                comparison='lt',
                threshold_value=0.5,
                duration_seconds=60,
                level=AlertLevel.WARNING,
                message_template="⚠️ Low confidence on {sensor_id}: {value:.1%}"
            ),
            
            # Temperature drift
            AlertThreshold(
                sensor_id='*',
                metric='temperature',
                comparison='range',
                threshold_value=15.0,
                threshold_max=35.0,
                duration_seconds=120,
                level=AlertLevel.WARNING,
                message_template="🌡️ Temperature out of range on {sensor_id}: {value:.1f}°C"
            ),
            
            # Signal saturation
            AlertThreshold(
                sensor_id='*',
                metric='state',
                comparison='eq',
                threshold_value=1,  # SATURATION state
                duration_seconds=10,
                level=AlertLevel.CRITICAL,
                message_template="📊 SENSOR SATURATION on {sensor_id}: Signal at maximum!"
            ),
            
            # Contamination detected
            AlertThreshold(
                sensor_id='*',
                metric='state',
                comparison='eq',
                threshold_value=2,  # CONTAMINATION state
                duration_seconds=0,
                level=AlertLevel.EMERGENCY,
                message_template="☠️ CONTAMINATION DETECTED on {sensor_id}!"
            ),
            
            # Long-term drift
            AlertThreshold(
                sensor_id='*',
                metric='drift_percent',
                comparison='gt',
                threshold_value=20.0,  # 20% drift
                duration_seconds=0,
                level=AlertLevel.WARNING,
                message_template="📈 Calibration drift detected on {sensor_id}: {value:.1f}%"
            )
        ]
        
        self.thresholds.extend(defaults)
    
    def add_threshold(self, threshold: AlertThreshold):
        """Add custom threshold"""
        self.thresholds.append(threshold)
    
    def evaluate(self, sensor_id: str, reading: dict) -> List[dict]:
        """
        Evaluate all thresholds against current reading.
        Returns list of triggered alerts.
        """
        triggered = []
        timestamp = reading.get('timestamp', time.time())
        
        for thresh in self.thresholds:
            # Skip if not applicable to this sensor
            if thresh.sensor_id != '*' and thresh.sensor_id != sensor_id:
                continue
            
            # Get metric value
            value = self._get_metric_value(reading, thresh.metric)
            if value is None:
                continue
            
            # Check condition
            condition_met = self._check_condition(value, thresh)
            
            if condition_met:
                condition_key = f"{sensor_id}:{thresh.metric}"
                
                # Track when condition started
                if condition_key not in self.condition_start:
                    self.condition_start[condition_key] = timestamp
                
                # Check duration requirement
                duration = timestamp - self.condition_start[condition_key]
                
                if duration >= thresh.duration_seconds:
                    # Check cooldown
                    last_alert = self.active_alerts.get(condition_key, 0)
                    if timestamp - last_alert >= thresh.cooldown_seconds:
                        alert = self._create_alert(sensor_id, thresh, value, duration)
                        triggered.append(alert)
                        
                        self.active_alerts[condition_key] = timestamp
                        self.alert_history.append(alert)
            else:
                # Condition no longer met
                condition_key = f"{sensor_id}:{thresh.metric}"
                if condition_key in self.condition_start:
                    del self.condition_start[condition_key]
        
        return triggered
    
    def _get_metric_value(self, reading: dict, metric: str):
        """Extract metric from reading"""
        if metric == 'value':
            return reading.get('normalized', reading.get('value'))
        elif metric == 'state':
            state_name = reading.get('state', '')
            # Map state names to numeric codes
            state_codes = {
                'SATURATION': 1,
                'CONTAMINATION': 2,
                'ANOMALY': 3
            }
            return state_codes.get(state_name, 0)
        return reading.get(metric)
    
    def _check_condition(self, value, thresh: AlertThreshold) -> bool:
        """Check if value satisfies threshold condition"""
        if thresh.comparison == 'gt':
            return value > thresh.threshold_value
        elif thresh.comparison == 'lt':
            return value < thresh.threshold_value
        elif thresh.comparison == 'eq':
            return value == thresh.threshold_value
        elif thresh.comparison == 'range':
            return not (thresh.threshold_value <= value <= thresh.threshold_max)
        return False
    
    def _create_alert(self, sensor_id: str, thresh: AlertThreshold, 
                      value, duration: float) -> dict:
        """Create alert object"""
        message = thresh.message_template.format(
            sensor_id=sensor_id,
            value=value,
            duration=duration
        )
        
        return {
            'timestamp': time.time(),
            'level': thresh.level.name,
            'sensor_id': sensor_id,
            'metric': thresh.metric,
            'value': value,
            'threshold': thresh.threshold_value,
            'message': message,
            'duration_s': duration
        }
    
    def register_handler(self, handler: Callable):
        """Register notification handler"""
        self.handlers.append(handler)
    
    async def dispatch_alert(self, alert: dict):
        """Dispatch alert to all handlers"""
        for handler in self.handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                print(f"Alert handler error: {e}")


# Built-in notification handlers

async def mqtt_alert_handler(alert: dict, mqtt_client):
    """Publish alert to MQTT topic"""
    topic = f"mycosentinel/alerts/{alert['level'].lower()}"
    mqtt_client.publish(topic, json.dumps(alert))

async def email_alert_handler(alert: dict, smtp_config: dict):
    """Send email for critical alerts"""
    if alert['level'] not in ['CRITICAL', 'EMERGENCY']:
        return
    
    msg = MIMEText(f"""
    MycoSentinel Alert: {alert['level']}
    
    Sensor: {alert['sensor_id']}
    Message: {alert['message']}
    Time: {datetime.fromtimestamp(alert['timestamp']).isoformat()}
    
    Value: {alert['value']}
    Threshold: {alert['threshold']}
    """)
    
    msg['Subject'] = f"[MycoSentinel] {alert['level']} Alert - {alert['sensor_id']}"
    msg['From'] = smtp_config['from']
    msg['To'] = smtp_config['to']
    
    with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
        server.starttls()
        server.login(smtp_config['username'], smtp_config['password'])
        server.send_message(msg)

async def telegram_alert_handler(alert: dict, bot_token: str, chat_id: str):
    """Send Telegram notification"""
    emoji_map = {
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'CRITICAL': '🚨',
        'EMERGENCY': '☠️'
    }
    
    text = f"""
{emoji_map.get(alert['level'], '🔔')} <b>{alert['level']}</b>

<b>Sensor:</b> <code>{alert['sensor_id']}</code>
<b>Message:</b> {alert['message']}
<b>Time:</b> {datetime.fromtimestamp(alert['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    import aiohttp
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        })
```

---

## Deployment Strategy

### 8.1 Docker Compose Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  # MQTT Broker (Eclipse Mosquitto)
  mqtt:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mqtt_data:/mosquitto/data
      - mqtt_logs:/mosquitto/log
    restart: unless-stopped

  # Time-Series Database
  influxdb:
    image: influxdb:2.7
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=secure-password
      - DOCKER_INFLUXDB_INIT_ORG=mycosentinel
      - DOCKER_INFLUXDB_INIT_BUCKET=biosensor_data
    volumes:
      - influxdb_data:/var/lib/influxdb2
    restart: unless-stopped

  # Dashboard API
  dashboard:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - INFLUXDB_URL=http://influxdb:8086
      - INFLUXDB_TOKEN=your-token
      - MQTT_BROKER=mqtt
      - MQTT_PORT=1883
    volumes:
      - ./models:/app/models:ro
      - ./config:/app/config:ro
    depends_on:
      - mqtt
      - influxdb
    restart: unless-stopped
    command: uvicorn dashboard:app --host 0.0.0.0 --port 8000

  # Edge Sensor Bridge (Raspberry Pi)
  sensor-bridge:
    build:
      context: .
      dockerfile: Dockerfile.edge
    privileged: true
    devices:
      - "/dev/i2c-1:/dev/i2c-1"
      - "/dev/spidev0.0:/dev/spidev0.0"
    environment:
      - MQTT_BROKER=mqtt
      - MQTT_PORT=1883
      - DEVICE_ID=${DEVICE_ID:-pi-001}
    depends_on:
      - mqtt
    restart: unless-stopped

  # Optional: Grafana for advanced visualization
  grafana:
    image: grafana/grafana:10
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - influxdb
    restart: unless-stopped

volumes:
  mqtt_data:
  mqtt_logs:
  influxdb_data:
  grafana_data:
```

### 8.2 Edge Device Deployment (Raspberry Pi)

```python
#!/usr/bin/env python3
"""
sensor_bridge.py - Edge device firmware for MycoSentinel
Runs on Raspberry Pi with connected biosensor hardware.
"""

import asyncio
import json
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import digitalio
import paho.mqtt.client as mqtt
from pathlib import Path

class SensorBridge:
    """
    Bridge between physical sensors and MQTT broker.
    Runs signal processing before sending to cloud.
    """
    
    def __init__(self, device_id: str, mqtt_broker: str, mqtt_port: int = 1883):
        self.device_id = device_id
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        
        # Initialize hardware
        self._init_hardware()
        
        # Initialize processors
        self.optical_config = OpticalConfig()
        self.optical_processor = OpticalProcessor(self.optical_config)
        
        self.electrical_config = ElectricalConfig()
        self.electrical_processor = ElectricalProcessor(self.electrical_config)
        
        # Temporal analyzer
        self.temporal_analyzer = TemporalAnalyzer(
            response_time_s=60.0,
            sampling_interval_s=1.0
        )
        
        # Anomaly detector (TFLite)
        self.anomaly_detector = None
        self._load_tflite_model()
        
        # MQTT
        self.mqtt = mqtt.Client()
        self.mqtt.on_connect = self._on_mqtt_connect
        self.mqtt.on_message = self._on_mqtt_message
        
        # Alert manager
        self.alert_manager = AlertManager()
        
    def _init_hardware(self):
        """Initialize I2C/SPI hardware interfaces"""
        try:
            # I2C for ADC (ADS1115)
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c)
            self.ads.gain = 1  # ±4.096V
            
            # ADC channels
            self.chan_optical = AnalogIn(self.ads, ADS.P0)  # Photodiode
            self.chan_electrical = AnalogIn(self.ads, ADS.P1)  # Working electrode
            self.chan_temp = AnalogIn(self.ads, ADS.P2)  # Thermistor
            
            # LED control (GPIO)
            self.led_gpio = digitalio.DigitalInOut(board.D18)
            self.led_gpio.direction = digitalio.Direction.OUTPUT
            self.led_gpio.value = False
            
            print("Hardware initialized successfully")
        except Exception as e:
            print(f"Hardware initialization error: {e}")
            raise
    
    def _load_tflite_model(self):
        """Load TFLite anomaly detection model"""
        model_path = Path("/app/models/anomaly_detector.tflite")
        if model_path.exists():
            try:
                self.anomaly_detector = TFLiteInferenceEngine(str(model_path))
                print("TFLite model loaded")
            except Exception as e:
                print(f"Failed to load TFLite model: {e}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        print(f"Connected to MQTT broker: {rc}")
        client.subscribe(f"mycosentinel/commands/{self.device_id}")
        
    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT commands"""
        try:
            cmd = json.loads(msg.payload.decode())
            action = cmd.get('action')
            
            if action == 'calibrate':
                self._run_calibration()
            elif action == 'reset':
                self._reset_baseline()
            elif action == 'dark_frame':
                self.optical_processor.capture_dark_frame(self)
                
        except Exception as e:
            print(f"Command error: {e}")
    
    def set_led_state(self, state: bool):
        """Control excitation LED"""
        self.led_gpio.value = state
        
    def read_raw_optical(self) -> float:
        """Read raw optical sensor value"""
        # Turn on LED
        self.set_led_state(True)
        time.sleep(0.05)  # LED warm-up
        
        # Read photodiode
        voltage = self.chan_optical.voltage
        
        # Turn off LED
        self.set_led_state(False)
        
        return voltage
    
    def read_raw_electrical(self) -> float:
        """Read electrical sensor (working electrode)"""
        return self.chan_electrical.voltage
    
    def read_temperature(self) -> float:
        """Read temperature from thermistor"""
        voltage = self.chan_temp.voltage
        # Thermistor calculation (NTC 10k)
        # V = Vcc * R_thermistor / (R_thermistor + R_series)
        # Simplified: convert voltage to temperature
        resistance = 10000 * voltage / (3.3 - voltage)
        # Simplified Steinhart-Hart
        temp_c = 1 / (0.001129148 + 0.000234125 * (resistance / 10000) + 
                      0.0000000876741 * (resistance / 10000) ** 3) - 273.15
        return temp_c
    
    async def read_sensors_loop(self):
        """Main sensor reading loop"""
        buffer = []
        
        while True:
            try:
                timestamp = time.time()
                temp = self.read_temperature()
                
                # Optical reading
                optical_raw = self.read_raw_optical()
                optical_result = self.optical_processor.process(
                    optical_raw * 1000,  # Convert V to mV for processing
                    temp
                )
                
                # Electrical reading
                electrical_raw = self.read_raw_electrical()
                electrical_result = self.electrical_processor.process(
                    int(electrical_raw / 3.3 * 65535),  # Convert to ADC
                    temp
                )
                
                # Temporal analysis
                combined_value = optical_result['normalized'] * 0.7 + \
                               electrical_result['normalized_response'] * 0.3
                
                temporal = self.temporal_analyzer.update(timestamp, combined_value)
                
                # Anomaly detection
                buffer.append({
                    'normalized': combined_value,
                    'temperature': temp,
                    'timestamp': timestamp
                })
                
                anomaly_result = {'anomaly': False, 'score': 0.0}
                if len(buffer) >= 60 and self.anomaly_detector:
                    anomaly_result = self._run_anomaly_detection(buffer)
                    buffer = buffer[-60:]  # Keep last 60
                
                # Combine results
                result = {
                    'timestamp': timestamp,
                    'device_id': self.device_id,
                    'optical': optical_result,
                    'electrical': electrical_result,
                    'temporal': temporal,
                    'anomaly': anomaly_result,
                    'value': combined_value,
                    'temperature': temp,
                    'state': temporal.get('state'),
                    'confidence': temporal.get('confidence', 0)
                }
                
                # Publish to MQTT
                self.mqtt.publish(
                    f"mycosentinel/sensors/{self.device_id}",
                    json.dumps(result)
                )
                
                # Check alerts
                alerts = self.alert_manager.evaluate(self.device_id, result)
                for alert in alerts:
                    await self.alert_manager.dispatch_alert(alert)
                
                await asyncio.sleep(1)  # 1 Hz sampling
                
            except Exception as e:
                print(f"Sensor loop error: {e}")
                await asyncio.sleep(5)
    
    def _run_anomaly_detection(self, buffer: list) -> dict:
        """Run TFLite anomaly detection"""
        try:
            # Prepare sequence
            sequence = np.zeros((1, 60, 4))
            for i, reading in enumerate(buffer[-60:]):
                sequence[0, i, 0] = reading['normalized']
                sequence[0, i, 1] = reading['temperature'] / 50.0
                if i > 0:
                    sequence[0, i, 2] = buffer[-60+i]['normalized'] - buffer[-60+i-1]['normalized']
                hour = (reading['timestamp'] % 86400) / 86400
                sequence[0, i, 3] = np.sin(hour * 2 * np.pi)
            
            prediction = self.anomaly_detector.predict(sequence)
            mse = np.mean(np.square(sequence - prediction))
            
            # Threshold from training
            threshold = 0.05  # Adjust based on your data
            
            return {
                'anomaly': mse > threshold,
                'score': float(mse),
                'threshold': threshold
            }
            
        except Exception as e:
            print(f"Anomaly detection error: {e}")
            return {'anomaly': False, 'score': 0.0}
    
    async def run(self):
        """Main entry point"""
        self.mqtt.connect(self.mqtt_broker, self.mqtt_port, 60)
        self.mqtt.loop_start()
        
        await self.read_sensors_loop()


if __name__ == "__main__":
    import os
    
    device_id = os.getenv('DEVICE_ID', 'pi-001')
    mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
    mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
    
    bridge = SensorBridge(device_id, mqtt_broker, mqtt_port)
    asyncio.run(bridge.run())
```

### 8.3 Installation Script

```bash
#!/bin/bash
# install.sh - MycoSentinel Edge Device Setup

set -e

echo "🍄 MycoSentinel Edge Installation"
echo "================================="

# Check if running on Raspberry Pi
if [[ ! -f /etc/os-release ]] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi"
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y python3-pip python3-venv i2c-tools libcamera-dev

# Enable I2C and SPI
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
mkdir -p ~/mycosentinel
cd ~/mycosentinel
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install numpy scipy tensorflow pillow fastapi uvicorn paho-mqtt influxdb-client
pip install adafruit-blinka adafruit-circuitpython-ads1x15

# Create directories
mkdir -p models config logs data

# Download pre-trained TFLite model (or train your own)
echo "📥 Downloading pre-trained models..."
curl -L -o models/anomaly_detector.tflite \
    https://github.com/yourusername/mycosentinel/releases/download/v1.0/anomaly_detector.tflite

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/mycosentinel.service << 'EOF'
[Unit]
Description=MycoSentinel Biosensor Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/mycosentinel
Environment=PATH=/home/pi/mycosentinel/venv/bin
Environment=DEVICE_ID=$(cat /proc/sys/kernel/hostname)
Environment=MQTT_BROKER=localhost
Environment=MQTT_PORT=1883
ExecStart=/home/pi/mycosentinel/venv/bin/python /home/pi/mycosentinel/sensor_bridge.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Configure MQTT broker address in /etc/systemd/system/mycosentinel.service"
echo "2. Copy your biosensor hardware drivers to ~/mycosentinel/"
echo "3. Start service: sudo systemctl enable --now mycosentinel"
echo "4. View logs: sudo journalctl -u mycosentinel -f"
echo ""
echo "Dashboard available at: http://$(hostname -I | awk '{print $1}'):8000/dashboard"
```

---

## Project Structure

```
mycosentinel/
├── docker-compose.yml          # Full stack deployment
├── Dockerfile                  # Dashboard service
├── Dockerfile.edge             # Edge device image
├── install.sh                  # Edge device installer
├── requirements.txt
│
├── src/
│   ├── signal_processing/
│   │   ├── __init__.py
│   │   ├── optical.py          # OpticalProcessor
│   │   ├── electrical.py       # ElectricalProcessor
│   │   └── calibration.py      # Calibrator classes
│   │
│   ├── temporal/
│   │   ├── __init__.py
│   │   ├── analyzer.py         # TemporalAnalyzer
│   │   └── drift.py            # DriftDetector
│   │
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── anomaly_detector.py # TFLite anomaly detection
│   │   └── calibration.py      # Online calibration
│   │
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── api.py              # FastAPI app
│   │   └── dashboard.html      # Web interface
│   │
│   ├── alerts/
│   │   ├── __init__.py
│   │   └── manager.py          # AlertManager
│   │
│   └── edge/
│       ├── __init__.py
│       └── sensor_bridge.py    # RPi bridge firmware
│
├── config/
│   ├── mosquitto.conf         # MQTT broker config
│   └── thresholds.json        # Alert threshold overrides
│
├── models/
│   ├── anomaly_detector.tflite
│   └── calibration_curve.json
│
└── tests/
    ├── test_optical.py
    ├── test_temporal.py
    └── test_anomaly.py
```

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Edge Device** | Raspberry Pi 3B+ | Raspberry Pi 4 (4GB) |
| **OS** | Raspberry Pi OS Lite (64-bit) | Raspberry Pi OS Full |
| **Storage** | 8GB SD | 32GB SD |
| **Python** | 3.9 | 3.11 |
| **RAM** | 512MB | 2GB |
| **Network** | WiFi | Ethernet |

---

## Performance Benchmarks

| Task | RPi 3B+ | RPi 4 | Intel N100 |
|------|---------|-------|------------|
| Optical Processing | 5ms | 2ms | <1ms |
| TFLite Inference | 45ms | 12ms | 3ms |
| Full Pipeline (1 reading) | 52ms | 18ms | 5ms |
| Max Sampling Rate | ~15 Hz | ~50 Hz | ~200 Hz |

---

## Security Considerations

1. **MQTT Authentication**: Enable username/password or TLS certificates
2. **InfluxDB Tokens**: Use read-only tokens for dashboard, write-only for edge
3. **Network Isolation**: Run IoT devices on isolated VLAN
4. **Firmware Signing**: Sign and verify edge firmware updates
5. **Secrets Management**: Use environment variables or secrets manager

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status |
| `/dashboard` | GET | Web dashboard |
| `/api/sensors` | GET | List all sensors |
| `/api/sensors/{id}/history` | GET | Historical data |
| `/ws` | WebSocket | Real-time updates |

---

## MQTT Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `mycosentinel/sensors/{id}` | Pub | Sensor readings |
| `mycosentinel/alerts/{level}` | Pub | Alert notifications |
| `mycosentinel/commands/{id}` | Sub | Device commands |
| `mycosentinel/calibration/{id}` | Pub | Calibration updates |

---

## License

MIT License - See LICENSE file

---

**Author:** BIOSYN-03 (ML Systems Engineer)  
**Version:** 1.0.0  
**Last Updated:** 2026-03-28
