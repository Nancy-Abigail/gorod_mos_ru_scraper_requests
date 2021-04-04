SELECT *
FROM   t_reports r LEFT JOIN
       t_objects o ON r.object_id = o.id LEFT JOIN
       t_authors a on r.author_id = a.id