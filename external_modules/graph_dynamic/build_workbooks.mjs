import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.dirname(fileURLToPath(import.meta.url)) + path.sep;
const data = JSON.parse(await fs.readFile(`${root}outputs/workbook_data_v1.json`, "utf8"));

const colors = {header:"#173F5F", sub:"#20639B", pale:"#EAF2F8", text:"#17202A"};
function colName(n){let s=""; while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s}
function norm(v){ if(Array.isArray(v)) return v.join(", "); if(v===null||v===undefined) return ""; if(typeof v==="object") return JSON.stringify(v); return v; }
function addSheet(wb,name,rows){
  const sh=wb.worksheets.add(name); sh.showGridLines=false;
  if(!rows?.length){sh.getRange("A1").values=[["无可靠数据"]]; return sh;}
  const headers=[...new Set(rows.flatMap(r=>Object.keys(r)))];
  const matrix=[headers,...rows.map(r=>headers.map(h=>norm(r[h])))];
  sh.getRangeByIndexes(0,0,matrix.length,headers.length).values=matrix;
  const end=colName(headers.length); const used=sh.getRange(`A1:${end}${matrix.length}`);
  sh.getRange(`A1:${end}1`).format={fill:colors.header,font:{bold:true,color:"#FFFFFF"},wrapText:true,borders:{preset:"outside",style:"thin",color:"#173F5F"}};
  used.format.font={name:"Microsoft YaHei",size:10,color:colors.text};
  used.format.wrapText=true; used.format.autofitColumns();
  for(let c=0;c<headers.length;c++) sh.getRangeByIndexes(0,c,matrix.length,1).format.columnWidth=Math.min(35,Math.max(12,headers[c].length*2+2));
  sh.getRange(`A1:${end}${matrix.length}`).format.borders={insideHorizontal:{style:"thin",color:"#DDE6ED"}};
  sh.freezePanes.freezeRows(1); if(headers.length>2) sh.freezePanes.freezeColumns(1);
  return sh;
}
async function save(wb,path,previewSheet){
  const inspect=await wb.inspect({kind:"sheet,table",maxChars:2500,tableMaxRows:3,tableMaxCols:8}); console.log(inspect.ndjson);
  const errors=await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:100},summary:"final formula error scan"}); console.log(errors.ndjson);
  const preview=await wb.render({sheetName:previewSheet,range:"A1:P25",scale:1,format:"png"});
  await fs.writeFile(path.replace(/\.xlsx$/,"_preview.png"),new Uint8Array(await preview.arrayBuffer()));
  const blob=await SpreadsheetFile.exportXlsx(wb); await blob.save(path);
}

const nodes=Workbook.create();
for(const name of ["Jobs","Skills","JDs","Companies","Domains"]) addSheet(nodes,name,data.nodes[name]);
await save(nodes,`${root}outputs/graph_nodes_v1.xlsx`,"Jobs");

const edges=Workbook.create();
for(const name of ["Job_Skill","JD_Job","JD_Skill","Job_Domain","Company_JD"]) addSheet(edges,name,data.edges[name]);
await save(edges,`${root}outputs/graph_edges_v1.xlsx`,"Job_Skill");

const profiles=Workbook.create(); addSheet(profiles,"重点岗位能力画像",data.profiles);
await save(profiles,`${root}outputs/key_job_graph_profiles_v1.xlsx`,"重点岗位能力画像");

const evolution=Workbook.create(); addSheet(evolution,"岗位技能演化",data.evolution);
await save(evolution,`${root}outputs/job_skill_evolution_v1.xlsx`,"岗位技能演化");
