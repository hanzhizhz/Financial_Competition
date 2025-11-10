import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderState = "idle" | "recording" | "processing" | "error";

export interface RecorderResult {
  file: File;
  duration: number; // milliseconds
  byteLength: number;
  sampleRate: number;
  mimeType: string;
}

export interface UseAudioRecorderOptions {
  sampleRate?: number;
  minDurationMs?: number;
  maxDurationMs?: number;
}

interface RecorderError {
  message: string;
  code?: string;
}

const DEFAULT_SAMPLE_RATE = 16000;
const DEFAULT_MIN_DURATION = 1200; // 1.2 seconds
const DEFAULT_MAX_DURATION = 5 * 60 * 1000; // 5 minutes

const MERGE_CHUNK_SIZE = 4096;

const floatTo16BitPCM = (input: Float32Array): Int16Array => {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    let s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
};

const writeWavHeader = (view: DataView, sampleRate: number, numSamples: number): void => {
  let offset = 0;

  const writeString = (str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
    offset += str.length;
  };

  const writeUint32 = (data: number) => {
    view.setUint32(offset, data, true);
    offset += 4;
  };

  const writeUint16 = (data: number) => {
    view.setUint16(offset, data, true);
    offset += 2;
  };

  writeString("RIFF");
  writeUint32(36 + numSamples * 2);
  writeString("WAVE");
  writeString("fmt ");
  writeUint32(16);
  writeUint16(1); // PCM
  writeUint16(1); // mono
  writeUint32(sampleRate);
  writeUint32(sampleRate * 2);
  writeUint16(2);
  writeUint16(16);
  writeString("data");
  writeUint32(numSamples * 2);
};

const mergeFloat32Chunks = (chunks: Float32Array[], totalSamples: number): Float32Array => {
  const result = new Float32Array(totalSamples);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
};

const downsampleBuffer = (buffer: Float32Array, sourceSampleRate: number, targetSampleRate: number): Float32Array => {
  if (targetSampleRate === sourceSampleRate) {
    return buffer;
  }

  if (targetSampleRate > sourceSampleRate) {
    throw new Error("目标采样率必须小于等于原始采样率");
  }

  const ratio = sourceSampleRate / targetSampleRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);

  let resultOffset = 0;
  let bufferOffset = 0;

  while (resultOffset < result.length) {
    const nextBufferOffset = Math.round((resultOffset + 1) * ratio);
    let sum = 0;
    let count = 0;

    for (let i = bufferOffset; i < nextBufferOffset && i < buffer.length; i++) {
      sum += buffer[i];
      count++;
    }

    result[resultOffset] = count > 0 ? sum / count : 0;
    resultOffset++;
    bufferOffset = nextBufferOffset;
  }

  return result;
};

const encodeWav = (samples: Float32Array, sampleRate: number): ArrayBuffer => {
  const pcm16 = floatTo16BitPCM(samples);
  const buffer = new ArrayBuffer(44 + pcm16.length * 2);
  const view = new DataView(buffer);

  writeWavHeader(view, sampleRate, pcm16.length);

  let offset = 44;
  for (let i = 0; i < pcm16.length; i++, offset += 2) {
    view.setInt16(offset, pcm16[i], true);
  }

  return buffer;
};

export const useAudioRecorder = (options: UseAudioRecorderOptions = {}) => {
  const sampleRate = options.sampleRate ?? DEFAULT_SAMPLE_RATE;
  const minDurationMs = options.minDurationMs ?? DEFAULT_MIN_DURATION;
  const maxDurationMs = options.maxDurationMs ?? DEFAULT_MAX_DURATION;

  const [state, setState] = useState<RecorderState>("idle");
  const [recordingTime, setRecordingTime] = useState(0);
  const [error, setError] = useState<RecorderError | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const timerRef = useRef<number | null>(null);
  const startTimestampRef = useRef<number | null>(null);
  const recordedSamplesRef = useRef<Float32Array[]>([]);
  const recordedSamplesCountRef = useRef(0);
  const actualSampleRateRef = useRef<number>(sampleRate);

  const reset = useCallback(() => {
    recordedSamplesRef.current = [];
    recordedSamplesCountRef.current = 0;
    startTimestampRef.current = null;
    setRecordingTime(0);
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const cleanupStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        try {
          track.stop();
        } catch (e) {
          console.warn("[useAudioRecorder] 停止音频轨道失败", e);
        }
      });
      streamRef.current = null;
    }
  }, []);

  const cleanupAudioGraph = useCallback(async () => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current.onaudioprocess = null;
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        await audioContextRef.current.close();
      } catch (e) {
        console.warn("[useAudioRecorder] 关闭 AudioContext 失败", e);
      }
      audioContextRef.current = null;
    }
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = useCallback(() => {
    stopTimer();
    timerRef.current = window.setInterval(() => {
      setRecordingTime(prev => prev + 1);
    }, 1000);
  }, [stopTimer]);

  const startRecording = useCallback(async (): Promise<void> => {
    if (state === "recording") {
      return;
    }

    setError(null);

    try {
      const constraints: MediaStreamConstraints = {
        audio: {
          channelCount: 1,
          sampleRate,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate });
      audioContextRef.current = audioContext;
      actualSampleRateRef.current = audioContext.sampleRate;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const bufferSize = MERGE_CHUNK_SIZE;
      const processor = audioContext.createScriptProcessor(bufferSize, source.channelCount, 1);
      processorRef.current = processor;

      recordedSamplesRef.current = [];
      recordedSamplesCountRef.current = 0;

      processor.onaudioprocess = (event: AudioProcessingEvent) => {
        const inputBuffer = event.inputBuffer;
        const channelData = inputBuffer.numberOfChannels > 1
          ? averageChannels(inputBuffer)
          : inputBuffer.getChannelData(0);

        const chunk = new Float32Array(channelData.length);
        chunk.set(channelData);
        recordedSamplesRef.current.push(chunk);
        recordedSamplesCountRef.current += chunk.length;
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      startTimestampRef.current = Date.now();
      setRecordingTime(0);
      startTimer();
      setState("recording");
    } catch (err: any) {
      console.error("[useAudioRecorder] 无法开始录音", err);
      setError({
        message: err?.message || "无法开始录音，请检查麦克风权限",
        code: err?.name
      });
      setState("error");
      await cleanupAudioGraph();
      cleanupStream();
      reset();
      throw err;
    }
  }, [cleanupAudioGraph, cleanupStream, reset, sampleRate, startTimer, state]);

  const stopRecording = useCallback(async (): Promise<RecorderResult | null> => {
    if (state !== "recording") {
      return null;
    }

    setState("processing");
    stopTimer();

    const startedAt = startTimestampRef.current ?? Date.now();
    const duration = Date.now() - startedAt;

    await cleanupAudioGraph();
    cleanupStream();

    const totalSamples = recordedSamplesCountRef.current;
    if (!totalSamples) {
      const message = "未捕获到音频数据，请重试";
      setError({ message, code: "NO_AUDIO" });
      setState("idle");
      reset();
      return null;
    }

    if (duration < minDurationMs) {
      const message = `录音时间太短（${(duration / 1000).toFixed(1)}s），请至少录制 ${(minDurationMs / 1000).toFixed(1)} 秒`;
      setError({ message, code: "AUDIO_TOO_SHORT" });
      setState("idle");
      reset();
      return null;
    }

    if (duration > maxDurationMs) {
      const message = "录音时间过长，请重新录制";
      setError({ message, code: "AUDIO_TOO_LONG" });
      setState("idle");
      reset();
      return null;
    }

    try {
      const mergedBuffer = mergeFloat32Chunks(recordedSamplesRef.current, totalSamples);
      const inputSampleRate = actualSampleRateRef.current;
      const resampledBuffer = inputSampleRate === sampleRate
        ? mergedBuffer
        : downsampleBuffer(mergedBuffer, inputSampleRate, sampleRate);

      const wavBuffer = encodeWav(resampledBuffer, sampleRate);
      const file = new File([wavBuffer], `recording_${Date.now()}.wav`, { type: "audio/wav" });

      const result: RecorderResult = {
        file,
        duration,
        byteLength: wavBuffer.byteLength,
        sampleRate,
        mimeType: "audio/wav"
      };

      setState("idle");
      reset();
      return result;
    } catch (err: any) {
      console.error("[useAudioRecorder] 处理音频数据失败", err);
      setError({ message: err?.message || "处理音频失败，请重试", code: "PROCESSING_ERROR" });
      setState("error");
      reset();
      return null;
    }
  }, [cleanupAudioGraph, cleanupStream, maxDurationMs, minDurationMs, reset, sampleRate, state, stopTimer]);

  const cancelRecording = useCallback(async () => {
    stopTimer();
    await cleanupAudioGraph();
    cleanupStream();
    reset();
    setState("idle");
  }, [cleanupAudioGraph, cleanupStream, reset, stopTimer]);

  const clearError = useCallback(() => setError(null), []);

  useEffect(() => {
    return () => {
      cancelRecording();
    };
  }, [cancelRecording]);

  return {
    state,
    recordingTime,
    error,
    startRecording,
    stopRecording,
    cancelRecording,
    clearError
  };
};

const averageChannels = (inputBuffer: AudioBuffer): Float32Array => {
  const channelData = new Float32Array(inputBuffer.length);
  const channels = inputBuffer.numberOfChannels;
  for (let channel = 0; channel < channels; channel++) {
    const input = inputBuffer.getChannelData(channel);
    for (let i = 0; i < input.length; i++) {
      channelData[i] += input[i];
    }
  }

  for (let i = 0; i < channelData.length; i++) {
    channelData[i] /= channels;
  }

  return channelData;
};

export type UseAudioRecorderReturn = ReturnType<typeof useAudioRecorder>;
