<?php

namespace Helper;

/**
 * Git integration helpers.
 */
class Git extends \Prefab
{
    /**
     * Links (commits and pull requests) associated with an issue.
     *
     * @return array<int,array>
     */
    public function links(int $issueId): array
    {
        if ($issueId <= 0) {
            return [];
        }

        try {
            return \Base::instance()->get('db.instance')->exec(
                'SELECT provider, repo, kind, external_id, url, state, meta_json, created_at
                 FROM issue_link
                 WHERE issue_id = ?
                 ORDER BY id DESC
                 LIMIT 20',
                [$issueId]
            );
        } catch (\Throwable $e) {
            return [];
        }
    }
}
