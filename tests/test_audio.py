import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from gestureos.audio.feedback import AudioFeedback, FeedbackSound, synthesize_tone


def test_synthesize_tone_returns_correct_sample_count() -> None:
    wave = synthesize_tone(440.0, 0.1, sample_rate=44100)

    assert wave.shape[0] == 4410


def test_synthesize_tone_is_stereo() -> None:
    wave = synthesize_tone(440.0, 0.05)

    assert wave.shape[1] == 2


def test_synthesize_tone_is_int16() -> None:
    wave = synthesize_tone(440.0, 0.05)

    assert wave.dtype.name == "int16"


def test_synthesize_tone_fades_to_near_zero_at_the_end() -> None:
    wave = synthesize_tone(440.0, 0.1)

    # Fade-out means the last handful of samples should be much
    # quieter than the loudest samples earlier in the tone.
    tail_amplitude = abs(int(wave[-1][0]))
    peak_amplitude = int(abs(wave[:, 0]).max())
    assert tail_amplitude < peak_amplitude * 0.1


def test_disabled_feedback_never_initializes_the_mixer() -> None:
    feedback = AudioFeedback(enabled=False)

    started = feedback.start()

    assert started is False


def test_enabled_feedback_starts_successfully_headless() -> None:
    feedback = AudioFeedback(enabled=True, volume=0.5)

    started = feedback.start()

    assert started is True
    feedback.stop()


def test_play_before_start_does_not_raise() -> None:
    feedback = AudioFeedback(enabled=True)

    feedback.play(FeedbackSound.CLICK)  # never started — must be a no-op


def test_play_after_start_does_not_raise() -> None:
    feedback = AudioFeedback(enabled=True)
    feedback.start()

    feedback.play(FeedbackSound.CLICK)
    feedback.play(FeedbackSound.RELEASE)
    feedback.play(FeedbackSound.SWITCH)
    feedback.play(FeedbackSound.ERROR)

    feedback.stop()


def test_play_when_disabled_does_not_raise() -> None:
    feedback = AudioFeedback(enabled=False)
    feedback.start()

    feedback.play(FeedbackSound.CLICK)  # no-op, must not raise


def test_stop_clears_cached_sounds() -> None:
    feedback = AudioFeedback(enabled=True)
    feedback.start()

    feedback.stop()

    assert feedback._sounds == {}
    assert feedback._ready is False
