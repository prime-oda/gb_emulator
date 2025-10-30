"""
Game Boy APU (Audio Processing Unit)
Handles sound generation and audio processing for the Game Boy emulator.

Cython最適化: Phase 2
"""

import pygame
import numpy as np
import threading
import time
from collections import deque

try:
    import cython
except ImportError:
    # Cythonがない環境でも動作するようにダミークラス
    class cython:
        @staticmethod
        def declare(*args, **kwargs):
            pass
        int = int
        longlong = int
        bint = bool


class APU:
    def __init__(self, memory, debug: cython.bint = False):
        self.memory = memory
        self.debug: cython.bint = debug
        
        # 🎵 高品質音声設定 - 44.1kHz対応
        self.sample_rate = 44100     # Game Boy準拠の高品質サンプルレート
        self.buffer_size = 1024      # より大きなバッファで安定性向上
        self.channels = 2            # ステレオ出力
        
        # Game Boy audio timing - 正確な計算
        self.gb_sample_rate = 4194304 // 95  # ~44kHz (Game Boy実機相当)
        self.cycles_per_sample = 4194304 // self.sample_rate  # 95.09サイクル/サンプル
        self.cycle_counter = 0
        
        # 🎵 Frame Sequencer実装 (512Hz)
        self.frame_sequencer_counter = 0
        self.frame_sequencer_step = 0  # 0-7の8ステップサイクル
        self.cycles_per_frame = 4194304 // 512  # 8192サイクル
        
        # Audio channels
        self.channel1 = SquareChannel(1, debug=debug)  # Square wave with sweep
        self.channel2 = SquareChannel(2, debug=debug)  # Square wave
        self.channel3 = WaveChannel(debug=debug)       # Wave channel  
        self.channel4 = NoiseChannel(debug=debug)      # Noise channel
        
        # Master control
        self.enabled = False
        self.left_volume = 7
        self.right_volume = 7
        
        # Output mixing
        self.left_enables = 0x00   # Which channels go to left speaker
        self.right_enables = 0x00  # Which channels go to right speaker
        
        # Audio buffer
        self.audio_buffer = deque(maxlen=self.buffer_size * 4)

        # Batch processing: APUは割り込みを発生させないため大きな値
        self._cycles_to_interrupt = 0x7FFFFFFFFFFFFFFF  # 最大値

        # Initialize pygame mixer
        self.init_audio()
        
    def init_audio(self):
        """Initialize pygame audio system"""
        try:
            pygame.mixer.pre_init(
                frequency=self.sample_rate,
                size=-16,  # 16-bit signed
                channels=self.channels,
                buffer=self.buffer_size
            )
            pygame.mixer.init()
            
            # Start audio playback thread
            self.audio_thread = threading.Thread(target=self._audio_thread, daemon=True)
            self.audio_running = True
            self.audio_thread.start()
            
            if self.debug:
                print(f"APU initialized: {self.sample_rate}Hz, {self.channels} channels")
                
        except pygame.error as e:
            print(f"Failed to initialize audio: {e}")
            self.audio_running = False
    
    def _audio_thread(self):
        """Audio playback thread"""
        # Create a single sound object to avoid creating new ones constantly
        dummy_array = np.zeros((self.buffer_size, 2), dtype=np.int16)
        current_sound = pygame.sndarray.make_sound(dummy_array)
        
        while self.audio_running:
            if len(self.audio_buffer) >= self.buffer_size * 2:  # Stereo
                # Get audio data from buffer
                samples = []
                for _ in range(self.buffer_size * 2):
                    if self.audio_buffer:
                        samples.append(self.audio_buffer.popleft())
                    else:
                        samples.append(0)
                
                # Convert to pygame sound (reshape for stereo)
                try:
                    audio_array = np.array(samples, dtype=np.int16).reshape(-1, 2)
                    sound = pygame.sndarray.make_sound(audio_array)
                    
                    # Only play if the previous sound finished or if the queue is getting full
                    if not pygame.mixer.get_busy() or len(self.audio_buffer) > self.buffer_size * 4:
                        pygame.mixer.Sound.play(sound)
                        
                except Exception as e:
                    if self.debug:
                        print(f"Audio error: {e}")
                    time.sleep(0.1)  # Longer delay on error
                    continue
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
    
    def step(self, cpu_cycles):
        """Update APU state based on CPU cycles - Frame Sequencer対応"""
        if not self.enabled:
            return
            
        self.cycle_counter += cpu_cycles
        
        # 🎵 Frame Sequencer更新 (512Hz)
        self.frame_sequencer_counter += cpu_cycles
        while self.frame_sequencer_counter >= self.cycles_per_frame:
            self.frame_sequencer_counter -= self.cycles_per_frame
            self._update_frame_sequencer()
        
        # Generate samples when enough cycles have passed
        while self.cycle_counter >= self.cycles_per_sample:
            self.cycle_counter -= self.cycles_per_sample
            self._generate_sample()

    
    def _update_frame_sequencer(self):
        """Frame Sequencer更新 - Game Boy準拠の512Hz制御"""
        step = self.frame_sequencer_step
        
        # Length Counter: 256Hz (step 0, 2, 4, 6)
        if step % 2 == 0:
            self.channel1.update_length_counter()
            self.channel2.update_length_counter()
            self.channel3.update_length_counter()
            self.channel4.update_length_counter()
        
        # Envelope: 64Hz (step 7)
        if step == 7:
            self.channel1.update_envelope()
            self.channel2.update_envelope()
            # Channel3にはエンベロープなし
            self.channel4.update_envelope()
        
        # Sweep: 128Hz (step 2, 6) - Channel1のみ
        if step == 2 or step == 6:
            self.channel1.update_sweep()
        
        # 次のステップへ
        self.frame_sequencer_step = (self.frame_sequencer_step + 1) % 8
    
    def _generate_sample(self):
        """Generate one audio sample"""
        # Update all channels
        self.channel1.step()
        self.channel2.step() 
        self.channel3.step()
        self.channel4.step()
        
        # Mix channels
        left_sample = 0
        right_sample = 0
        
        if self.left_enables & 0x01:  # Channel 1 to left
            left_sample += self.channel1.get_sample()
        if self.left_enables & 0x02:  # Channel 2 to left
            left_sample += self.channel2.get_sample()
        if self.left_enables & 0x04:  # Channel 3 to left
            left_sample += self.channel3.get_sample()
        if self.left_enables & 0x08:  # Channel 4 to left
            left_sample += self.channel4.get_sample()
            
        if self.right_enables & 0x01:  # Channel 1 to right
            right_sample += self.channel1.get_sample()
        if self.right_enables & 0x02:  # Channel 2 to right
            right_sample += self.channel2.get_sample()
        if self.right_enables & 0x04:  # Channel 3 to right
            right_sample += self.channel3.get_sample()
        if self.right_enables & 0x08:  # Channel 4 to right
            right_sample += self.channel4.get_sample()
        
        # Apply master volume
        left_sample = (left_sample * (self.left_volume + 1)) // 8
        right_sample = (right_sample * (self.right_volume + 1)) // 8
        
        # Clamp to 16-bit range
        left_sample = max(-32768, min(32767, left_sample))
        right_sample = max(-32768, min(32767, right_sample))
        
        # Add to buffer
        if len(self.audio_buffer) < self.audio_buffer.maxlen - 2:
            self.audio_buffer.append(left_sample)
            self.audio_buffer.append(right_sample)
    
    def write_register(self, address, value):
        """Write to APU register"""
        # Removed debug output for performance
            
        if address == 0xFF24:  # NR50 - Channel control / ON-OFF / Volume
            self.left_volume = (value >> 4) & 0x07
            self.right_volume = value & 0x07
            
        elif address == 0xFF25:  # NR51 - Selection of Sound output terminal
            self.left_enables = (value >> 4) & 0x0F
            self.right_enables = value & 0x0F
            
        elif address == 0xFF26:  # NR52 - Sound on/off
            old_enabled = self.enabled
            self.enabled = bool(value & 0x80)
            
            if not self.enabled:
                # Disable all channels
                self.channel1.enabled = False
                self.channel2.enabled = False
                self.channel3.enabled = False  
                self.channel4.enabled = False
            elif not old_enabled:
                # Reset all channels when re-enabling
                self.channel1.reset()
                self.channel2.reset()
                self.channel3.reset()
                self.channel4.reset()
                
        # Channel 1 (Square with sweep)
        elif 0xFF10 <= address <= 0xFF14:
            self.channel1.write_register(address, value)
            
        # Channel 2 (Square)  
        elif 0xFF16 <= address <= 0xFF19:
            self.channel2.write_register(address, value)
            
        # Channel 3 (Wave)
        elif 0xFF1A <= address <= 0xFF1E:
            self.channel3.write_register(address, value)
            
        # Channel 4 (Noise)
        elif 0xFF20 <= address <= 0xFF23:
            self.channel4.write_register(address, value)
            
        # Wave pattern RAM
        elif 0xFF30 <= address <= 0xFF3F:
            self.channel3.write_wave_ram(address - 0xFF30, value)
    
    def read_register(self, address):
        """Read from APU register"""
        if address == 0xFF24:  # NR50
            return (self.left_volume << 4) | self.right_volume
            
        elif address == 0xFF25:  # NR51
            return (self.left_enables << 4) | self.right_enables
            
        elif address == 0xFF26:  # NR52
            status = 0x80 if self.enabled else 0x00
            if self.channel1.enabled:
                status |= 0x01
            if self.channel2.enabled:
                status |= 0x02
            if self.channel3.enabled:
                status |= 0x04
            if self.channel4.enabled:
                status |= 0x08
            return status
            
        # Channel registers
        elif 0xFF10 <= address <= 0xFF14:
            return self.channel1.read_register(address)
        elif 0xFF16 <= address <= 0xFF19:
            return self.channel2.read_register(address)
        elif 0xFF1A <= address <= 0xFF1E:
            return self.channel3.read_register(address)
        elif 0xFF20 <= address <= 0xFF23:
            return self.channel4.read_register(address)
        elif 0xFF30 <= address <= 0xFF3F:
            return self.channel3.read_wave_ram(address - 0xFF30)
            
        return 0xFF


class SquareChannel:
    def __init__(self, channel_num, debug=False):
        self.channel_num = channel_num
        self.debug = debug
        self.enabled = False
        
        # Wave generation
        self.frequency = 0
        self.duty_cycle = 0  # 0=12.5%, 1=25%, 2=50%, 3=75%
        self.phase = 0
        
        # Envelope
        self.envelope_volume = 0
        self.envelope_direction = 0  # 0=decrease, 1=increase
        self.envelope_period = 0
        self.envelope_counter = 0
        self.current_volume = 0
        
        # Length counter
        self.length_enabled = False
        self.length_counter = 0
        
        # Sweep (Channel 1 only)
        self.sweep_enabled = (channel_num == 1)
        self.sweep_period = 0
        self.sweep_direction = 0  # 0=increase, 1=decrease  
        self.sweep_shift = 0
        self.sweep_counter = 0
        
        # Duty cycle patterns
        self.duty_patterns = [
            [0, 0, 0, 0, 0, 0, 0, 1],  # 12.5%
            [1, 0, 0, 0, 0, 0, 0, 1],  # 25%
            [1, 0, 0, 0, 0, 1, 1, 1],  # 50%
            [0, 1, 1, 1, 1, 1, 1, 0],  # 75%
        ]
        
    def reset(self):
        """Reset channel to default state"""
        self.enabled = False
        self.phase = 0
        self.current_volume = 0
        self.envelope_counter = 0
        self.length_counter = 0
        self.sweep_counter = 0
    
    def step(self):
        """Update channel state - 高精度周波数計算"""
        if not self.enabled:
            return
            
        # 🎵 正確な周波数計算 - Game Boy準拠
        if self.frequency > 0:
            # Game Boy式: Period = (2048-frequency)*4
            period = (2048 - self.frequency) * 4
            if period > 0:
                freq_hz = 4194304 / period  # Game Boy クロック周波数
                phase_increment = (freq_hz * 8) / 44100  # 8ステップ/デューティサイクル
                self.phase += phase_increment
                if self.phase >= 8:
                    self.phase -= 8

    
    def update_length_counter(self):
        """Length Counter更新 - Frame Sequencerから呼び出し"""
        if self.length_enabled and self.length_counter > 0:
            self.length_counter -= 1
            if self.length_counter == 0:
                self.enabled = False
    
    def update_envelope(self):
        """Envelope更新 - Frame Sequencerから呼び出し"""
        if self.envelope_period > 0:
            if self.envelope_direction:
                if self.current_volume < 15:
                    self.current_volume += 1
            else:
                if self.current_volume > 0:
                    self.current_volume -= 1
    
    def update_sweep(self):
        """Sweep更新 - Channel1のみ、Frame Sequencerから呼び出し"""
        if not self.sweep_enabled or self.sweep_period == 0:
            return
            
        old_freq = self.frequency
        if self.sweep_direction:
            self.frequency -= self.frequency >> self.sweep_shift
        else:
            self.frequency += self.frequency >> self.sweep_shift
        
        # 周波数オーバーフローチェック
        if self.frequency > 2047:
            self.enabled = False
    
    def get_sample(self):
        """Get current audio sample"""
        if not self.enabled or self.current_volume == 0:
            return 0
            
        # Get duty cycle output
        duty_index = int(self.phase) % 8
        duty_output = self.duty_patterns[self.duty_cycle][duty_index]
        
        # Apply volume
        sample = duty_output * self.current_volume * 2000  # Scale for audible output
        return sample
    
    def write_register(self, address, value):
        """Write to channel register"""
        offset = address - (0xFF10 if self.channel_num == 1 else 0xFF16)
        
        if offset == 0 and self.sweep_enabled:  # NR10 (Channel 1 only)
            self.sweep_period = (value >> 4) & 0x07
            self.sweep_direction = (value >> 3) & 0x01
            self.sweep_shift = value & 0x07
            
        elif offset == 1:  # NR11/NR21 - Duty and length
            self.duty_cycle = (value >> 6) & 0x03
            self.length_counter = 64 - (value & 0x3F)
            
        elif offset == 2:  # NR12/NR22 - Envelope
            self.envelope_volume = (value >> 4) & 0x0F
            self.envelope_direction = (value >> 3) & 0x01
            self.envelope_period = value & 0x07
            self.current_volume = self.envelope_volume
            
        elif offset == 3:  # NR13/NR23 - Frequency low
            self.frequency = (self.frequency & 0x700) | value
            
        elif offset == 4:  # NR14/NR24 - Frequency high and control
            self.frequency = (self.frequency & 0xFF) | ((value & 0x07) << 8)
            self.length_enabled = bool(value & 0x40)
            
            if value & 0x80:  # Trigger
                self.enabled = True
                if self.length_counter == 0:
                    self.length_counter = 64
                self.current_volume = self.envelope_volume
                self.envelope_counter = 0
                self.phase = 0
    
    def read_register(self, address):
        """Read from channel register"""
        # Most registers are write-only, return 0xFF
        return 0xFF


class WaveChannel:
    def __init__(self, debug=False):
        self.debug = debug
        self.enabled = False
        self.dac_enabled = False
        
        # Wave generation
        self.frequency = 0
        self.phase = 0
        self.volume_level = 0  # 0=mute, 1=100%, 2=50%, 3=25%
        
        # Length counter
        self.length_enabled = False
        self.length_counter = 0
        
        # Wave RAM (32 4-bit samples)
        self.wave_ram = [0] * 16  # 16 bytes = 32 4-bit samples
        
    def reset(self):
        """Reset channel to default state"""
        self.enabled = False
        self.phase = 0
        self.length_counter = 0
        
    def step(self):
        """Update channel state - 高精度周波数計算"""
        if not self.enabled or not self.dac_enabled:
            return
            
        # 🎵 正確な周波数計算 - Game Boy準拠
        if self.frequency > 0:
            # Game Boy式: Period = (2048-frequency)*2 (Wave channelは*2)
            period = (2048 - self.frequency) * 2
            if period > 0:
                freq_hz = 4194304 / period
                phase_increment = (freq_hz * 32) / 44100  # 32サンプル/Wave RAM
                self.phase += phase_increment
                if self.phase >= 32:
                    self.phase -= 32

    
    def update_length_counter(self):
        """Length Counter更新 - Frame Sequencerから呼び出し"""
        if self.length_enabled and self.length_counter > 0:
            self.length_counter -= 1
            if self.length_counter == 0:
                self.enabled = False
    
    def get_sample(self):
        """Get current audio sample"""
        if not self.enabled or not self.dac_enabled or self.volume_level == 0:
            return 0
            
        # Get sample from wave RAM
        sample_index = int(self.phase) % 32
        byte_index = sample_index // 2
        nibble = sample_index % 2
        
        if nibble == 0:
            sample = (self.wave_ram[byte_index] >> 4) & 0x0F
        else:
            sample = self.wave_ram[byte_index] & 0x0F
        
        # Apply volume level
        if self.volume_level == 1:
            sample = sample
        elif self.volume_level == 2:
            sample = sample >> 1
        elif self.volume_level == 3:
            sample = sample >> 2
        else:
            sample = 0
        
        # Scale for output
        return (sample - 7) * 1000  # Center around 0 and scale
    
    def write_register(self, address, value):
        """Write to channel register"""
        offset = address - 0xFF1A
        
        if offset == 0:  # NR30 - DAC enable
            self.dac_enabled = bool(value & 0x80)
            if not self.dac_enabled:
                self.enabled = False
                
        elif offset == 1:  # NR31 - Length
            self.length_counter = 256 - value
            
        elif offset == 2:  # NR32 - Volume
            self.volume_level = (value >> 5) & 0x03
            
        elif offset == 3:  # NR33 - Frequency low
            self.frequency = (self.frequency & 0x700) | value
            
        elif offset == 4:  # NR34 - Frequency high and control
            self.frequency = (self.frequency & 0xFF) | ((value & 0x07) << 8)
            self.length_enabled = bool(value & 0x40)
            
            if value & 0x80:  # Trigger
                self.enabled = self.dac_enabled
                if self.length_counter == 0:
                    self.length_counter = 256
                self.phase = 0
    
    def read_register(self, address):
        """Read from channel register"""
        return 0xFF
    
    def write_wave_ram(self, offset, value):
        """Write to wave RAM"""
        if offset < 16:
            self.wave_ram[offset] = value
    
    def read_wave_ram(self, offset):
        """Read from wave RAM"""
        if offset < 16:
            return self.wave_ram[offset]
        return 0xFF


class NoiseChannel:
    def __init__(self, debug=False):
        self.debug = debug
        self.enabled = False
        
        # Noise generation
        self.lfsr = 0x7FFF  # 15-bit linear feedback shift register
        self.clock_divider = 0
        self.counter_step = 0  # 0=15-bit, 1=7-bit
        self.dividing_ratio = 0
        
        # Envelope
        self.envelope_volume = 0
        self.envelope_direction = 0
        self.envelope_period = 0
        self.envelope_counter = 0
        self.current_volume = 0
        
        # Length counter
        self.length_enabled = False
        self.length_counter = 0
        
        # Timing
        self.noise_counter = 0
        
    def reset(self):
        """Reset channel to default state"""
        self.enabled = False
        self.lfsr = 0x7FFF
        self.current_volume = 0
        self.envelope_counter = 0
        self.length_counter = 0
        self.noise_counter = 0
    
    def step(self):
        """Update channel state - 高精度ノイズ生成"""
        if not self.enabled:
            return
            
        # 🎵 正確なノイズ周波数計算
        self.noise_counter += 1
        noise_freq = self._get_noise_frequency()
        if noise_freq > 0 and self.noise_counter >= (44100 // noise_freq):
            self.noise_counter = 0
            self._update_lfsr()

    
    def update_length_counter(self):
        """Length Counter更新 - Frame Sequencerから呼び出し"""
        if self.length_enabled and self.length_counter > 0:
            self.length_counter -= 1
            if self.length_counter == 0:
                self.enabled = False
    
    def update_envelope(self):
        """Envelope更新 - Frame Sequencerから呼び出し"""
        if self.envelope_period > 0:
            if self.envelope_direction:
                if self.current_volume < 15:
                    self.current_volume += 1
            else:
                if self.current_volume > 0:
                    self.current_volume -= 1
    
    def _get_noise_frequency(self):
        """Calculate noise frequency"""
        if self.dividing_ratio == 0:
            divisor = 8
        else:
            divisor = 16 * self.dividing_ratio
            
        return 524288 // (divisor * (2 ** (self.clock_divider + 1)))
    
    def _update_lfsr(self):
        """Update linear feedback shift register"""
        bit0 = self.lfsr & 1
        bit1 = (self.lfsr >> 1) & 1
        result = bit0 ^ bit1
        
        self.lfsr = (self.lfsr >> 1) | (result << 14)
        
        if self.counter_step:  # 7-bit mode
            self.lfsr = (self.lfsr & ~0x40) | (result << 6)
    
    def get_sample(self):
        """Get current audio sample"""
        if not self.enabled or self.current_volume == 0:
            return 0
            
        # Get output from LFSR (invert bit 0)
        output = (~self.lfsr) & 1
        
        # Apply volume
        sample = output * self.current_volume * 1500
        return sample
    
    def write_register(self, address, value):
        """Write to channel register"""
        offset = address - 0xFF20
        
        if offset == 1:  # NR41 - Length
            self.length_counter = 64 - (value & 0x3F)
            
        elif offset == 2:  # NR42 - Envelope
            self.envelope_volume = (value >> 4) & 0x0F
            self.envelope_direction = (value >> 3) & 0x01
            self.envelope_period = value & 0x07
            self.current_volume = self.envelope_volume
            
        elif offset == 3:  # NR43 - Polynomial counter
            self.clock_divider = (value >> 4) & 0x0F
            self.counter_step = (value >> 3) & 0x01
            self.dividing_ratio = value & 0x07
            
        elif offset == 4:  # NR44 - Control
            self.length_enabled = bool(value & 0x40)
            
            if value & 0x80:  # Trigger
                self.enabled = True
                if self.length_counter == 0:
                    self.length_counter = 64
                self.current_volume = self.envelope_volume
                self.envelope_counter = 0
                self.lfsr = 0x7FFF
                self.noise_counter = 0
    
    def read_register(self, address):
        """Read from channel register"""
        return 0xFF