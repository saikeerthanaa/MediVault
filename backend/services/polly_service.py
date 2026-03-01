import boto3

class PollyService:
    def __init__(self, region: str):
        self.client = boto3.client("polly", region_name=region)

    def synthesize(self, text: str, voice_id: str = "Aditi", output_format: str = "mp3"):
        resp = self.client.synthesize_speech(
            Text=text,
            OutputFormat=output_format,
            VoiceId=voice_id
        )

        audio_stream = resp.get("AudioStream")
        if not audio_stream:
            return {"ok": False, "error": "No AudioStream returned"}

        return {
            "ok": True,
            "audio_bytes": audio_stream.read()
        }