# Security policy

InkToFilm invokes FFmpeg on user-selected media files. Use current FFmpeg releases and do not analyze
untrusted media in a privileged environment. Suite video paths are restricted to the suite directory
to reduce accidental filesystem exposure.

## Semantic evaluator privacy

InkToFilm does not upload videos or run a semantic provider by default. Selecting
`--semantic-command` explicitly gives that local command access to the prompt and sampled frames;
the command may in turn use a remote model. Keep provider credentials in environment variables and
never place tokens or private URLs in suites, results, reports, or commits.

Please report vulnerabilities privately through GitHub Security Advisories rather than a public
issue.
