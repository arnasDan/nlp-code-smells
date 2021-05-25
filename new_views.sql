CREATE MATERIALIZED VIEW solution_smells AS
WITH empty_catch_blocks AS (
	SELECT
		p."Solution_id" AS solution_id,
		COUNT(*) AS count
	FROM
		implementation_smell s,
		project p
	WHERE
		p.Id = s."Project_id" 
		AND s.Name IN ('Empty Catch Block', 'Empty catch clause')
	GROUP BY solution_id
), complex_methods AS (
	SELECT
		p."Solution_id" AS solution_id,
		COUNT(*) AS count
	FROM
		implementation_smell s,
		project p
	WHERE
		p.Id = s."Project_id" 
		AND s.Name = 'Complex Method'
	GROUP BY solution_id
), magic_numbers AS (
	SELECT
		p."Solution_id" AS solution_id,
		COUNT(*) AS count
	FROM
		implementation_smell s,
		project p
	WHERE
		p.Id = s."Project_id" 
		AND s.Name = 'Magic Number'
	GROUP BY solution_id
), multifacted_abstractions_solution AS (
	SELECT
		p."Solution_id" AS solution_id,
		COUNT(*) AS count
	FROM
		design_smell s,
		project p
	WHERE
		p.Id = s."Project_id" 
		AND s.Name = 'Multifaceted Abstraction'
	GROUP BY solution_id
)
SELECT
	dp.name,
	dp.repository_link,
	dp.prog_language,
	s.upload_date,
	s.id AS solution_id,
	ecb.count AS "Empty Catch Block",
	cm.count AS "Complex Method",
	mn.count AS "Magic Number",
	ma.count AS "Multifaceted Abstraction"
FROM
	designite_project dp,
	solution s,
	empty_catch_blocks ecb,
	complex_methods cm,
	magic_numbers mn,
	multifacted_abstractions_solution ma
WHERE
	s."Designite_Project_id" = dp.Id
	AND ecb.solution_id = s.Id
	AND cm.solution_id = s.Id
	AND mn.solution_id = s.Id
	AND ma.solution_id = s.Id;
	
CREATE MATERIALIZED VIEW smells AS (
SELECT
	p."Solution_id" AS solution_id,
	'implementation' AS type,
	s.name,
	s._class AS "class",
	s.component,
	s.method
FROM 
	implementation_smell s,
	project p
WHERE
	s."Project_id" = p.Id
UNION ALL
SELECT 
	p."Solution_id" AS solution_id,
	'design' AS type, 
	s.name, s._class AS "class", 
	s.component, 
	NULL AS method 
FROM
	design_smell s,
	project p
WHERE s."Project_id" = p.Id
	
CREATE INDEX smell_soluton
	ON smells (solution_id);