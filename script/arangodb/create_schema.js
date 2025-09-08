const db = require('@arangodb').db;
var gg = require("@arangodb/general-graph");

// 配置

const tables = [
    // 关系模型
    "author",
    "work",
    "topic",
    "institution",
    "institution_geo",
    // 文档模型
    "work_doc",
    "author_doc",
    // 向量模型
    "work_vec",
    "topic_vec"
]

const graphs = [
    {
        name: 'work_work_gra',
        info: {
            collection: 'work_referenced_work_e',
            from: ['work_v'],
            to: ['work_v']
        }
    },
    {
        name: 'work_topic_gra',
        info: {
            collection: 'work_topic_e',
            from: ['work_v'],
            to: ['topic_v']
        }
    },
    {
        name: 'work_author_gra',
        info: {
            collection: 'work_author_e',
            from: ['work_v'],
            to: ['author_v']
        }
    },
    {
        name: 'author_author_gra',
        info: {
            collection: 'author_author_e',
            from: ['author_v'],
            to: ['author_v']
        }
    }
]

// 建表

for (let t of tables) {
    if (!db._collection(t)) {
        db._createDocumentCollection(t);
        print(`创建表${t}`)
    } else {
        db._truncate(t);
        print(`清空表${t}`)
    }
}


// 建立图

for (let g of graphs) {
    if (!gg._exists(g.name)) {
        gg._create(g.name, [g.info])
        print(`创建图${g.name}`)
    } else {
        // 清空
        db._truncate(g.info.collection);
        print(`清空边表${g.info.collection}`)
        db._truncate(g.info.from[0]);
        print(`清空点表${g.info.from[0]}`)
        db._truncate(g.info.to[0]);
        print(`清空点表${g.info.to[0]}`)
    }
}