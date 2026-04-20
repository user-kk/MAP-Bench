DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_extension
        WHERE extname = 'ldbc'
    ) THEN
        RAISE NOTICE '扩展 ldbc 未找到，正在创建...';
        EXECUTE 'CREATE EXTENSION ldbc';
        RAISE NOTICE '扩展 ldbc 创建完成';
    ELSE
        RAISE NOTICE '扩展 ldbc 已安装，无需处理';
    END IF;
END
$$;

select load_graph('work_work_gra'::regclass::bigint);
select load_graph('work_topic_gra'::regclass::bigint);
select load_graph('work_author_gra'::regclass::bigint);
select load_graph('author_author_gra'::regclass::bigint);



