const db = require('@arangodb').db;

/* 1. 给所有集合的 id 建 persistent 唯一索引 */
// 关系
db.author.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.author.ensureIndex({ type: "persistent", fields: ["institution_id"], unique: false, inBackground: true });
db.work.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.topic.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.institution.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.institution_geo.ensureIndex({ type: "persistent", fields: ["institution_id"], unique: true, inBackground: true });
// 文档
db.work_doc.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.author_doc.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.author_doc.ensureIndex({   type: "hash", fields: ["doc.display_name_alternatives[*]"] });
db.work_doc.ensureIndex({   type: "hash", fields: ["doc.topics[*].display_name"] });
// 图 
db.work_v.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.topic_v.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.author_v.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
// 向量
db.work_vec.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });
db.topic_vec.ensureIndex({ type: "persistent", fields: ["id"], unique: true, inBackground: true });

/* 2. 给向量集合的 vec 字段建向量索引（维度 128，l2距离，按需改） */
db.work_vec.ensureIndex({
    type: "vector", fields: ["vec"], params: {
        dimension: 128, metric: "l2", nLists: 4096, defaultNProbe:50
    },
    inBackground: true
});
db.topic_vec.ensureIndex({
    type: "vector", fields: ["vec"], params: {
        dimension: 128, metric: "l2", nLists: 128, defaultNProbe:10
    },
    inBackground: true
});

print("=== 所有索引创建完成 ===");