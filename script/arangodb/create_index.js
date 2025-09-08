const db = require('@arangodb').db;

/* 1. 给所有集合的 id 建 hash 唯一索引（等值查询用） */
db.author.ensureIndex({ type: "hash", fields: ["id"], unique: true });
db.work.ensureIndex({ type: "hash", fields: ["id"], unique: true });
db.topic.ensureIndex({ type: "hash", fields: ["id"], unique: true });
db.institution.ensureIndex({ type: "hash", fields: ["id"], unique: true });
db.institution_geo.ensureIndex({ type: "hash", fields: ["institution_id"], unique: true });
db.work_doc.ensureIndex({ type: "hash", fields: ["id"], unique: true });
db.author_doc.ensureIndex({ type: "hash", fields: ["id"], unique: true });

/* 2. 给向量集合的 vec 字段建向量索引（维度 128，l2距离，按需改） */
db.work_vec.ensureIndex({
    type: "vector", fields: ["vec"], params: {
        dimension: 128, metric: "l2", nLists: 100,
        defaultNProbe: 1,
        trainingIterations: 25
    }
});
db.topic_vec.ensureIndex({
    type: "vector", fields: ["vec"], params: {
        dimension: 128, metric: "l2", nLists: 100,
        defaultNProbe: 1,
        trainingIterations: 25
    }
});

print("=== 所有索引创建完成 ===");