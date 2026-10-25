-- Gold `skeleton_role_counts`: players per club and role, with the source URLs they came from (C10).
SELECT
    club,
    role,
    count(*) AS n_players,
    list_sort(list_distinct(list(source_url))) AS source_urls
FROM skeleton_players
GROUP BY club, role
ORDER BY club, role
