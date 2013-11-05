http://www.hallvord.com/temp/moz/compatTesterTesting/contenttest.html

* Uses JS to output different content for different UA strings, including different linked CSS
* Both content and style tests should fail

http://hallvord.com/temp/moz/compatTesterTesting/redirtest.php
* UA-sniffing, HTTP redirect - should report redirect failure with details

http://www.hallvord.com/temp/moz/compatTesterTesting/csstest.html
* Inline CSS. Should output a single warning about .test2 definition

http://www.hallvord.com/temp/moz/compatTesterTesting/csstest2.html
* Linked CSS. Should output warnings about -webkit-box-pack and -webkit-transform
TODO: should really also warn against display: -webkit-box, but we don't have any code looking
at -webkit- in property values yet..

http://www.hallvord.com/temp/moz/compatTesterTesting/csstest3.html
* Uses CSS @import to include a stylesheet with problems. Should report same warnings
as csstest2.html
