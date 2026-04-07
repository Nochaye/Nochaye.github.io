// let number = prompt("input")
// if (number != null) {
//     alert("你输入了" + number)
// }

////////////////////////////////////

function writeSomething() {
    document.writeln("xiedongxi")    
}

//////////////////////////////////

let conga_list = ["新的一天，可爱加倍，烦恼清零","叮～你的好运已送达，今天超顺利超开心","阳光正好，微风不燥，你超棒超开心哒","叮～快乐已充值，今天可爱值拉满啦"]


function congadulation_daily(){
    let rand = Math.floor(Math.random() * (conga_list.length - 1))
    alert(conga_list[rand])
}

/////////////////////////////////////

function random_luck(){
    let max_size_luck = 100
    let rand = Math.floor(Math.random() * max_size_luck)
    alert("今日运气值：" + rand)
}