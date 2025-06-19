import subprocess
from datetime import datetime
import tempfile
from pathlib import Path
import json
from typing import Dict, Any, Optional, Union 

AVAILABLE_LANGUAGES = ['arabic', 'chinese', 'croatian', 'dutch', 'english', 'englishcoll', 'englishsci', 'estonian',
                       'french', 'german', 'italian', 'portuguese', 'russian', 'spanish', 'vietnamese']

AVAILABLE_DOCUMENT_TYPES = ['colloquial', 'narratives', 'news', 'scientific']
AVAILABLE_OUTPUT_TYPES = ['timeml', 'xmi']


class HeidelTime:
    def __init__(self, config: Union[Dict[str, Any], str, Path] = {}) -> None:
        """
        Initialize the HeidelTime java wrapper 
        
        Args:
           config: Configuration  dictionary, path to the JSON file or {} empty dict for Default 
        """
        # We have to load the configuration as first step
        self.config = self._loadconfig(config)

        
        # Path to the heidelTime standalone jar file
        heideltime_path = self.config.get("heideltime_path")

        if heideltime_path is None:
            raise ValueError("Please specify the path to Heideltime.standalone.jar in the configuration")
        self.heidel = Path(heideltime_path)
        
        if not self.heidel.exists():
            raise FileNotFoundError(f"HeidelTime jar file is not found at {self.heidel}")
        
        # Set the java executable path
        self.java = self.config.get("java_path", "java")
        
        # Parse and set the start date
        start_date_str = self.config.get("start_date")
        if start_date_str:
            try:
                self.start_date = datetime.strptime(start_date_str, "%Y/%m/%d").date()
            except ValueError:
                try:
                    # Fallback to original fomrat
                    self.start_date = datetime.strptime(start_date_str, "%y/%m/%d").date()
                except ValueError:
                    raise ValueError("start_date must be in format 'YYYY/MM/DD or YY/MM/DD'")
        else:
            self.start_date = datetime.now().date()

        # Set configuration file path
        conf_heideltime = self.config.get("conf_heideltime")

        if conf_heideltime is None:
            self.conf_heideltime = self.heidel / "config.props" # This is how to make a path using the path lib
        else: self.conf_heideltime = Path(conf_heideltime)
       
        # Set document processing parameters with validation
        self.doc_type = self.config.get("doc_type", "narratives")
        self.set_type(self.doc_type)
        
        # Fixed typo: "frensh" -> "french"
        self.lang = self.config.get("lang", "french")
        self.set_lang(self.lang)
        
        self.output_type = self.config.get("output_type", "TIMEML")
        self.out_type(self.output_type)
        
        self.encoding = self.config.get("encoding", "UTF-8")
        
        # Optional parameters
        self.verbosity = self.config.get("verbosity", False)
        self.interval_tagger = self.config.get("interval_tagger", False)
        self.locale = self.config.get("locale")
        self.pos_tagger = self.config.get("pos_tagger", "no")


    def _loadconfig(self, config: Union[Dict[str, Any], str, Path] = {}) -> Dict[str, Any]:
        """ Loading The configuration for various sources """
        if config is {}:
            return {}
        elif isinstance(config, Dict):
            return config
        elif isinstance(config, (str, Path)):
            config_path = Path(config)
            if not config_path.exists():
                raise FileNotFoundError(f"Configuration File for the wrapper is not found : {config_path}!")

            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON configuration file: {e}")
        else:
            raise TypeError("Configuration must be a dictionary, path string, or path Path object !!")


    def set_time(self, doc_time: str) -> None:
        """
            We expect here a time with the format "YYYY/MM/DD" or "YY/MM/DD" the default format in datetime lib 
            to specify the documents creation date (DCT), it's the date in witch we have 
            the anonymous date will be mapped
        """
        try:
            self.start_date = datetime.strptime(doc_time, "%Y/%m/%d")
        except ValueError:
            try:
                self.start_date = datetime.strptime(doc_time, "%y/%m/%d")
            except ValueError:
                raise ValueError(f"doc_time must be in format 'YYYY/MM/DD or YY/MM/DD'")


    def set_lang(self, lang: str) -> None:
        """
        Set the language of the parser. The supported Languages are presente in the AVAILABLE_LANGUAGES
        the default languges is frensh where this is the base use case for this wrapper.
        NOTE: The Arabic, chinese and croatian are not supported in this where they hae different
        taggers that need to be installed
        """
        if not lang.lower() in AVAILABLE_LANGUAGES:
            raise ValueError(f'Languague: " {lang} "is not supported in heideltime'
                f'Please chose one of the supported languagues:\n {AVAILABLE_LANGUAGES}')
        self.lang = lang.lower()

    def set_type(self, type: str) -> None:
        """
        Set the Document type presented in the AVAILABLE_DOCUMENT_TYPE, those type are in 
        HeidelTime specification
        """
        if not type.lower() in AVAILABLE_DOCUMENT_TYPES:
            raise ValueError(f'Document type: "{type}" is not specified !'
                f'Please select one of those documents type:\n{AVAILABLE_DOCUMENT_TYPES}')
        self.doc_type = type

    def out_type(self, o_type: str) -> None:
        """
        Set the output of the parser. HeidelTime support the TIMEML specification and XMI
        """
        if not o_type.lower() in AVAILABLE_OUTPUT_TYPES:
            raise ValueError(f'output type: {o_type} is not specified !'
                             f'Please select one of those output type\n{AVAILABLE_OUTPUT_TYPES}')
        self.output_type = o_type

    def set_encod(self, encod: str) -> None:
        "Encoding of the text, this is not clear"
        self.encoding = encod


    def set_config(self, conf_path: str, abs: bool) -> None:
        """
        Set the path to the configuration file, you can do absolute and relative path
        it should be relative to the standalone jar file not this python script
        """
        if not abs:
            self.conf_heideltime = self.heidel / conf_path
        else:
            self.conf_heideltime = Path(conf_path)

    # This we will not use anyway, I desided to put them here for compatibility
    def set_verbosity(self, verbosity: bool) -> None:
        self.verbosity = verbosity

    def set_interval_tagger(self, interval_tagger: bool) -> None:
        self.interval_tagger = interval_tagger

    def set_locale(self, locale: str) -> None:
        self.locale = locale

    def set_pos_tagger(self, pos_tagger: str) -> None:
        self.pos_tagger = pos_tagger


    def parse(self, doc: str = "") -> str:
        # We have to dafe the doc text in a file to pass it to HeidelTime
        # This is not the best thing to do where the r/w to the disk have risk
        # Moreover this is going to slow down the overall pipeline [MAYBE]

        if not doc:
            raise ValueError(f"No text provided to parse")

        with tempfile.NamedTemporaryFile(mode='w', encoding=self.encoding, 
                                       prefix='heideltime_', suffix='.tmp', 
                                       delete=False) as tmp_file:
            tmp_file.write(doc)
            tmp_file_path = tmp_file.name
        try:
            # We define the command to be executed
            jar_path = self.heidel / 'de.unihd.dbs.heideltime.standalone.jar'
            cmd = [self.java, 
                    '-jar', str(jar_path.absolute().as_posix()), 
                    tmp_file_path,
                    '-l', self.lang, 
                    '-t', self.doc_type,
                    '-o', self.output_type, 
                    '-c', self.conf_heideltime, 
                    '-e', self.encoding, 
                    '-dct', self.start_date.strftime("%Y-%m-%d")
                  ]
        
            if self.verbosity:
                cmd.append('-v')

            if self.interval_tagger:
                cmd.append('-it')

            if self.locale:
                cmd.append('-locale')
                cmd.append(self.locale)

            if self.pos_tagger:
                cmd.append('-pos')
                cmd.append(self.pos_tagger)
            try:
                result =  subprocess.check_output(cmd, stderr=subprocess.PIPE)
                return result.decode(self.encoding)
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode(self.encoding) if e.stderr else str(e)
                raise RuntimeError(f"HeidelTime execution failed: {error_msg}")
            
        finally:
            # Clean up temporary file
            Path(tmp_file_path).unlink(missing_ok=True)
