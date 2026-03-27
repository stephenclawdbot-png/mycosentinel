"""
Bioreactor hardware controller for fungal biosensors.
Manages environmental conditions for optimal yeast/fungal growth.
"""

import time
import threading
from dataclasses import dataclass
from typing import Optional, Callable
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BioreactorConditions:
    """Environmental conditions for fungal growth"""
    temperature_c: float = 25.0  # Optimal for S. cerevisiae
    humidity_percent: float = 60.0
    ph: float = 6.5
    light_exposure_lux: float = 0.0  # Keep dark for GFP expression
    nutrient_flow_ml_per_hour: float = 1.0

class BioreactorController:
    """
    Hardware controller for bioreactor vessel.
    
    Supports:
    - Temperature control (heating pad + fan)
    - Humidity control (ultrasonic mister)
    - pH monitoring (discrete sampling)
    - LED excitation for optical readout
    - Nutrient pump control
    """
    
    def __init__(
        self,
        temp_pin_heater: int = 18,  # GPIO18
        temp_pin_fan: int = 19,     # GPIO19
        mist_pin: int = 20,         # GPIO20
        led_pin: int = 21,          # GPIO21 (excitation)
        pump_pin: int = 22,         # GPIO22
        use_mock: bool = True       # Set False for real hardware
    ):
        self.conditions = BioreactorConditions()
        self.target_conditions = BioreactorConditions()
        self._running = False
        self._control_thread: Optional[threading.Thread] = None
        self._callbacks: list[Callable] = []
        self.use_mock = use_mock
        
        if not use_mock:
            try:
                import RPi.GPIO as GPIO
                self.GPIO = GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setup([temp_pin_heater, temp_pin_fan, mist_pin, led_pin, pump_pin], GPIO.OUT)
                self.pins = {
                    'heater': temp_pin_heater,
                    'fan': temp_pin_fan,
                    'mist': mist_pin,
                    'led': led_pin,
                    'pump': pump_pin
                }
            except ImportError:
                logger.warning("RPi.GPIO not available, using mock mode")
                self.use_mock = True
        
        logger.info("BioreactorController initialized (mock=%s)", self.use_mock)
    
    def register_callback(self, callback: Callable):
        """Register callback for condition updates"""
        self._callbacks.append(callback)
    
    def _read_temperature(self) -> float:
        """Read from DS18B20 temperature sensor"""
        if self.use_mock:
            # Simulate temperature drift toward target
            diff = self.target_conditions.temperature_c - self.conditions.temperature_c
            return self.conditions.temperature_c + (diff * 0.1)
        
        # Real hardware: read from /sys/bus/w1/devices/
        try:
            with open('/sys/bus/w1/devices/28-*/w1_slave', 'r') as f:
                lines = f.readlines()
                if 'YES' in lines[0]:
                    temp_str = lines[1].split('t=')[1]
                    return float(temp_str) / 1000.0
        except Exception as e:
            logger.error(f"Temperature read failed: {e}")
        return self.conditions.temperature_c
    
    def _set_heater(self, on: bool):
        """Control heating element"""
        if not self.use_mock:
            self.GPIO.output(self.pins['heater'], self.GPIO.HIGH if on else self.GPIO.LOW)
        logger.debug(f"Heater {'ON' if on else 'OFF'}")
    
    def _set_fan(self, on: bool):
        """Control cooling fan"""
        if not self.use_mock:
            self.GPIO.output(self.pins['fan'], self.GPIO.HIGH if on else self.GPIO.LOW)
        logger.debug(f"Fan {'ON' if on else 'OFF'}")
    
    def _trigger_mist(self, duration_ms: int = 500):
        """Trigger ultrasonic mister"""
        if not self.use_mock:
            self.GPIO.output(self.pins['mist'], self.GPIO.HIGH)
            time.sleep(duration_ms / 1000)
            self.GPIO.output(self.pins['mist'], self.GPIO.LOW)
        logger.debug(f"Mist triggered for {duration_ms}ms")
    
    def _trigger_led(self, duration_ms: int = 100):
        """Trigger excitation LED (e.g., 470nm for GFP)"""
        if not self.use_mock:
            self.GPIO.output(self.pins['led'], self.GPIO.HIGH)
            time.sleep(duration_ms / 1000)
            self.GPIO.output(self.pins['led'], self.GPIO.LOW)
        logger.debug(f"LED triggered for {duration_ms}ms")
    
    def _control_loop(self):
        """Main control loop - runs in thread"""
        while self._running:
            # Read current conditions
            self.conditions.temperature_c = self._read_temperature()
            
            # Temperature control with hysteresis
            temp_diff = self.target_conditions.temperature_c - self.conditions.temperature_c
            if temp_diff > 0.5:
                self._set_heater(True)
                self._set_fan(False)
            elif temp_diff < -0.5:
                self._set_heater(False)
                self._set_fan(True)
            else:
                self._set_heater(False)
                self._set_fan(False)
            
            # Humidity control (simplified)
            if self.conditions.humidity_percent < self.target_conditions.humidity_percent - 5:
                self._trigger_mist(500)
            
            # Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(self.conditions)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            time.sleep(1)  # 1Hz control loop
    
    def start(self):
        """Start control loop"""
        if self._running:
            return
        self._running = True
        self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self._control_thread.start()
        logger.info("Bioreactor control loop started")
    
    def stop(self):
        """Stop control loop"""
        self._running = False
        if self._control_thread:
            self._control_thread.join(timeout=5)
        logger.info("Bioreactor control loop stopped")
    
    def set_temperature(self, temp_c: float):
        """Set target temperature"""
        self.target_conditions.temperature_c = temp_c
        logger.info(f"Target temperature set to {temp_c}°C")
    
    def trigger_excitation(self, duration_ms: int = 100):
        """Trigger LED for optical readout"""
        self._trigger_led(duration_ms)
    
    def get_conditions(self) -> BioreactorConditions:
        """Get current conditions"""
        return self.conditions

if __name__ == "__main__":
    # Demo mode
    import signal
    
    reactor = BioreactorController(use_mock=True)
    reactor.set_temperature(30.0)
    
    def on_conditions_update(conds):
        print(f"Temp: {conds.temperature_c:.2f}°C, Humidity: {conds.humidity_percent:.1f}%")
    
    reactor.register_callback(on_conditions_update)
    reactor.start()
    
    def shutdown(sig, frame):
        print("\nShutting down...")
        reactor.stop()
        exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    
    print("Running demo (Ctrl+C to stop)...")
    while True:
        time.sleep(1)
