/*
 * @name: WJQING
 * @Date: 2022-08-22 13:39:37
 * @LastEditTime: 2022-09-01 09:56:20
 */
const fs = require('fs')
const path = require('path')
let index = 0;
let text = '';
function getFiles(dir) {
    const stat = fs.statSync(dir)
    if (stat.isDirectory()) {
        //判断是不是目录
        const dirs = fs.readdirSync(dir)
        dirs.forEach(value => {
            // console.log('路径',path.resolve(dir,value));
            getFiles(path.join(dir, value))
        })
    } else if (stat.isFile()) {
        //若不是Python文件则跳过
        if (!dir.endsWith('.py')) {
            return
        }
        console.log(`${index++}`, dir);
        fs.readFile(dir, (err, buffer) => {
            if (err) {
                console.log(err)
            } else {
                console.log(dir)
                // console.log(buffer.toString());
                fs.appendFileSync(`./program.docx`, `${buffer.toString()}`, err => { console.log(err, `错误数据,路径:${dir}`) })
                // fs.writeFileSync(`./program.docx`, `${buffer.toString()}`, err => { console.log(err) })
                // 增加一个空行以分割文件
                fs.appendFileSync(`./program.docx`, '\n', err => { console.log(err) })
            }
        })
    }
}
getFiles('./src/REvoDesign')


