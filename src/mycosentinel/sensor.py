"""
Sensor reading modules for optical fluorescence and electrical impedance.
Supports: Pi Camera (optical), ADC (electrical)
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)

@dataclass
class SensorReading:
    """Base sensor reading"""
    timestamp: float
    channel: int
    value: float
    confidence: float = 1.0

@dataclass
class OpticalReading(SensorReading):
    """Fluorescence intensity reading"""
    excitation_wavelength_nm: int = 470  # Blue LED for GFP
    emission_wavelength_nm: int = 509  # GFP emission
    integration_time_ms: int = 100
    roi: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h

@dataclass
class ElectricalReading(SensorReading):
    """Electrochemical reading (for electricigens)"""
    frequency_hz: float = 1.0
    impedance_ohm: Optional[float] = None
    voltage_v: float = 0.0
    current_uA: float = 0.0

class OpticalSensor:
    """
    Optical fluorescence sensor using Raspberry Pi Camera.
    
    Reads GFP fluorescence intensity from fungal cultures.
    GFP expression increases when target analyte detected.
    """
    
    def __init__(
        self,
        camera_resolution: Tuple[int, int] = (640, 480),
        roi: Optional[Tuple[int, int, int, int]] = None,
        use_mock: bool = True
    ):
        self.resolution = camera_resolution
        self.roi = roi or (100, 100, 200, 200)  # Default center ROI
        self.use_mock = use_mock
        self._capture = None
        
        if not use_mock:
            try:
                from picamera2 import Picamera2
                self.camera = Picamera2()
                config = self.camera.create_still_configuration(
                    main={"size": camera_resolution}
                )
                self.camera.configure(config)
                self.camera.start()
                time.sleep(2)  # Warmup
                logger.info("Pi Camera initialized")
            except ImportError:
                logger.warning("picamera2 not available, using mock mode")
                self.use_mock = True
    
    def capture(self, excitation_duration_ms: int = 100) -> OpticalReading:
        """
        Capture fluorescence image and extract intensity.
        
        Flow:
        1. Trigger excitation LED (blue)
        2. Capture image
        3. Extract ROI intensity
        4. Return reading
        """
        timestamp = time.time()
        
        # Trigger excitation (bioreactor controller handles hardware)
        # Capture image
        if self.use_mock:
            # Simulate signal with noise
            base_signal = 128  # 8-bit mid-gray
            noise = np.random.normal(0, 5)
            mock_intensity = max(0, min(255, base_signal + noise))
            
            return OpticalReading(
                timestamp=timestamp,
                channel=0,
                value=float(mock_intensity),
                confidence=0.8,
                integration_time_ms=excitation_duration_ms,
                roi=self.roi
            )
        
        # Real hardware capture
        image = self.camera.capture_array()
        
        # Extract ROI and calculate intensity
        x, y, w, h = self.roi
        roi_pixels = image[y:y+h, x:x+w]
        
        # Green channel (assuming BGR format)
        green_intensity = np.mean(roi_pixels[:, :, 1])
        
        # Calculate confidence based on pixel variance
        variance = np.var(roi_pixels[:, :, 1])
        confidence = min(1.0, 1.0 / (1.0 + variance / 100))
        
        return OpticalReading(
            timestamp=timestamp,
            channel=0,
            value=green_intensity,
            confidence=confidence,
            integration_time_ms=excitation_duration_ms,
            roi=self.roi
        )
    
    def calibrate_background(self, n_samples: int = 10) -> float:
        """Calibrate baseline fluorescence intensity"""
        readings = [self.capture().value for _ in range(n_samples)]
        baseline = np.mean(readings)
        logger.info(f"Background calibrated: {baseline:.2f}")
        return baseline

class ElectricalSensor:
    """
    Electrochemical sensor for electricigen detection.
    
    Measures impedance or current flow between electrodes.
    Electricigens (like Geobacter) produce current when metabolizing.
    """
    
    def __init__(
        self,
        adc_channel: int = 0,
        reference_voltage: float = 3.3,
        bits: int = 16,
        use_mock: bool = True
    ):
        self.channel = adc_channel
        self.vref = reference_voltage
        self.bits = bits
        self.use_mock = use_mock
        self._baseline = 0.0
        
        if not use_mock:
            try:
                import board
                import busio
                import adafruit_ads1x15.ads1115 as ADS
                from adafruit_ads1x15.analog_in import AnalogIn
                
                self.i2c = busio.I2C(board.SCL, board.SDA)
                self.ads = ADS.ADS1115(self.i2c)
                self.ads.gain = 1
                self.analog_in = AnalogIn(self.ads, ADS.P0, ADS.P1)
                logger.info("ADC initialized (ADS1115)")
            except ImportError as e:
                logger.warning(f"ADC hardware not available: {e}")
                self.use_mock = True
    
    def measure_voltage(self) -> float:
        """Read voltage from ADC (differential)"""
        if self.use_mock:
            # Simulate with drift
            base = 0.5 + self._baseline
            noise = np.random.normal(0, 0.01)
            drift = np.sin(time.time() * 0.1) * 0.1  # Slow drift
            return base + noise + drift
        
        # Real hardware
        return self.analog_in.voltage
    
    def measure(self, n_samples: int = 5, interval_ms: int = 100) -> ElectricalReading:
        """
        Take multiple readings and average.
        
        Returns voltage difference across biofilm.
        Current inferred from voltage drop across known resistor.
        """
        timestamp = time.time()
        samples = []
        
        for _ in range(n_samples):
            samples.append(self.measure_voltage())
            time.sleep(interval_ms / 1000)
        
        mean_voltage = np.mean(samples)
        std_voltage = np.std(samples)
        
        # Assume 1MΩ resistor in series, calculate current
        # I = V/R = (Vref - Vsample) / R_series
        r_series = 1_000_000  # 1M ohm
        current_uA = ((self.vref - mean_voltage) / r_series) * 1e6
        
        # Confidence based on signal stability
        confidence = max(0.0, 1.0 - (std_voltage / mean_voltage if mean_voltage > 0 else 1))
        
        return ElectricalReading(
            timestamp=timestamp,
            channel=self.channel,
            value=mean_voltage,
            confidence=confidence,
            voltage_v=mean_voltage,
            current_uA=current_uA
        )
    
    def calibrate_baseline(self, duration_sec: int = 60) -> float:
        """Calibrate baseline electrical signal"""
        logger.info(f"Calibrating baseline for {duration_sec}s...")
        
        samples = []
        start = time.time()
        while time.time() - start < duration_sec:
            samples.append(self.measure_voltage())
            time.sleep(1)
        
        self._baseline = np.mean(samples)
        logger.info(f"Baseline calibrated: {self._baseline:.4f}V")
        return self._baseline
    
    def detect_anomaly(self, reading: ElectricalReading, threshold_std: float = 3.0) -> bool:
        """Simple anomaly detection based on deviation from baseline"""
        if self._baseline == 0:
            return False
        
        deviation = abs(reading.value - self._baseline)
        # Simplified: assume 0.1V typical variation
        return deviation > (threshold_std * 0.1)

# Alias for easier import
Sensor = OpticalSensor  # Default to optical

if __name__ == "__main__":
    print("Sensor module demo")
    
    optical = OpticalSensor(use_mock=True)
    electrical = ElectricalSensor(use_mock=True)
    
    print("\nOptical readings:")
    for i in range(5):
        reading = optical.capture()
        print(f"  {i+1}: {reading.value:.1f} (confidence: {reading.confidence:.2f})")
        time.sleep(0.5)
    
    print("\nElectrical readings:")
    for i in range(5):
        reading = electrical.measure()
        print(f"  {i+1}: {reading.value:.4f}V, {reading.current_uA:.2f}µA (confidence: {reading.confidence:.2f})")
        time.sleep(0.5)
