CREATE TYPE source_type AS ENUM ('youtube', 'tv3', 'ib3', 'tiktok');
CREATE TYPE source_status AS ENUM ('new', 'downloading', 'downloaded', 'audio_extracting', 'audio_extracted', 'audio_converting', 'audio_converted', 'error');
CREATE TYPE clip_status AS ENUM ('new', 'splitting', 'split', 'validated');

CREATE TABLE IF NOT EXISTS sources(
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT,
    type source_type,
    videopath TEXT,
    audiopath TEXT,
    audiopath_16 TEXT,
    downloaded BOOL DEFAULT FALSE,
    converted BOOL DEFAULT FALSE,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS clips(
    clip_id UUID PRIMARY KEY,
    source_id UUID REFERENCES sources(source_id),
    filepath TEXT,
    "start" float4 NULL,
	"end" float4 NULL,
);

CREATE TABLE IF NOT EXISTS transcripts(
    transcript_id UUID PRIMARY KEY,
    text TEXT,
    transcriber CHAR(40),
    clip_id UUID REFERENCES clips(clip_id)
);

alter table clips add transcript_id UUID REFERENCES transcripts(transcript_id);

        
CREATE INDEX IF NOT EXISTS idx_sources_url ON public.sources USING btree (url);

create user grafana with encrypted password 'datapipe';
grant connect on database datapipe to grafana;
grant usage on database datapipe to grafana;
grant usage on schema public to grafana;
grant select on all tables in schema public to grafana;
grant select on all sequences in schema public to grafana;
alter default privileges in schema public grant select on tables to grafana;