SELECT cron.schedule(
  'qq-pocket-dispatch',
  '* * * * *',
  $job$
    SELECT net.http_post(
      url := 'https://qq-pocket.vercel.app/internal/tick',
      headers := jsonb_build_object('Content-Type','application/json','x-api-key',
        (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='qq_pocket_worker_key')),
      body := '{}'::jsonb,
      timeout_milliseconds := 20000
    ) WHERE EXISTS (
      SELECT 1 FROM qq_pocket.beta_jobs
      WHERE (status='queued' AND available<=extract(epoch FROM now()))
         OR (status='running' AND lease<extract(epoch FROM now()))
    );
  $job$
);
